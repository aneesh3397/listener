$(document).ready(function() {
    if (!window.console) window.console = {};
    if (!window.console.log) window.console.log = function() {};

    $("#messageform").on("submit", function() {
        newMessage($(this));
        return false;
    });
    $("#messageform").on("keypress", function(e) {
        if (e.keyCode == 13) {
            newMessage($(this));
            return false;
        }
    });
    $("#message").select();
    updater.start();
});

function newMessage(form) {
    var message = form.formToDict();
    updater.socket.send(JSON.stringify(message));
    form.find("input[type=text]").val("").select();
}

jQuery.fn.formToDict = function() {
    var fields = this.serializeArray();
    var json = {}
    for (var i = 0; i < fields.length; i++) {
        json[fields[i].name] = fields[i].value;
    }
    if (json.next) delete json.next;
    return json;
};

var width = parseInt(d3.select('#chart').style('width'))
var height = parseInt(d3.select('#chart').style('height'))
var padding = 10

var rect = [50,50, width - 50, height - 50];

var maxSpeed = 3
var radius = d3.scale.sqrt().range([3, 3])
var nodes = []

// set up SVG element:

const zoom = d3.behavior.zoom()
      .scaleExtent([1/4, 9])
      .on('zoom', function () {
        d3.select('g').attr('transform', d3.event.transform)
      });

var svg = d3.select('#chart')
      .append('svg')
      .attr('width', width)
      .attr('height',height)
      .call(d3.behavior.zoom().scaleExtent([1/4, 9]).on("zoom", function () {
        svg.attr("transform", "translate(" + d3.event.translate + ")" + " scale(" + d3.event.scale + ")")
      }))
      .append('g');

// set up scales:

var xScale = d3.scale.linear()
 					 .domain([d3.min(nodes, function(d) { return d['x']; }), d3.max(nodes, function(d) { return d['x']; })])
                     .range([padding, width-padding*2]); 

var yScale = d3.scale.linear()
 				     .domain([d3.min(nodes, function(d) { return d['y']; }), d3.max(nodes, function(d) { return d['y']; })])
                      .range([height-padding, padding]);
                      
var cValue = function(d) {
    if (d.cluster == 0){
        return d.cluster
        }
    else if (d.cluster % 10 == 0 && d.cluster > 0) {
        return  10
        }
    else{
        return d.cluster % 10
        }
    }

cluster_colors = ["#ffffff", "#33658A", "#83781B", "#FCAB10", "#6292AB", "#FF720C", "#942911", "#7A306C", "#95995E","#FE938C","#AC444D"]

// tooltip functions:

function mouseover(d) {
                
    d3.select("#tooltip")
      .style("left", d3.event.clientX + 20 + "px")
      .style("top", d3.event.clientY - 20 + "px")						
      .select("#value")
      .text(d.tweet)

    d3.select("#tooltip")
      .select("#value2")
      .style("color", d3.select(this).style("fill"))
      .text(d.top_terms);

      d3.select("#tooltip")
      .select("#value3")
      .text(d.cluster);
                               
    d3.select("#tooltip").classed("hidden", false);
}
                
function mouseout(d){
    d3.select("#tooltip").classed("hidden", true);
}

function add_naive_point(data){

    var force = d3.layout.force()

    new_point = {radius: 4,
                 tweet: data.tweet,
                 x: data.x, 
                 y: data.y,
                 cluster: data.cluster,
                 speedX: (Math.random() - 0.5) * 2 * maxSpeed,
                 speedY: (Math.random() - 0.5) * 2 * maxSpeed}
    
    nodes.push(new_point);

    force.nodes(nodes)
         .size([width, height])
         .gravity(0)
         .charge(0)
         .on("tick", tick)
         .start();
    
    var circle = svg.selectAll("circle")
                    .data(nodes)
                    .enter().append("circle")
                    .on("mouseover", mouseover)
                    .on("mouseout", mouseout)
                    .attr("r", function(d) { return d.radius; })
                    .attr("cx", function(d) { return (d.x); })
                    .attr("cy", function(d) { return (d.y); })
                    .style("fill", "#ffffff")
                    .call(force.drag);

    function tick(e) {
        force.alpha(0.1)
        circle.each(gravity(e.alpha))
              .each(collide(.5))
              .on("mouseover", mouseover)
              .on("mouseout", mouseout)
              .attr("cx", function(d) { return (d.x); })
              .attr("cy", function(d) { return (d.y); });
      }
}

function first_fix(data){
    console.log('first clustering')
    svg.selectAll("circle").each(function(d){ d.fixed=true; })

    current_positions = []
    d3.selectAll('circle').each(function () {
        const thisD3 = d3.select(this)
        current_positions.push([thisD3.attr('cx'), thisD3.attr('cy')])
      })

    svg.selectAll("circle").remove()

    svg.selectAll("circle")
            .data(current_positions.slice(0,data.length))
            .enter()
            .append("circle")
            .attr("cx", function(d) {return d[0]; })
            .attr("cy", function(d) {return d[1]; })
            .attr("r", 2)
            .style("fill", "#ffffff")

    xScale.domain([d3.min(data, function(d) { return d['x']; }), d3.max(data, function(d) { return d['x']; })])
    yScale.domain([d3.min(data, function(d) { return d['y']; }), d3.max(data, function(d) { return d['y']; })])

    svg.selectAll("circle")
        .data(data)
        .on("mouseover", mouseover)
        .on("mouseout", mouseout)
        .transition()
        .duration(1000)
        .attr("cx", function(d){
                return xScale(d['x']);
            })
        .attr("cy", function(d){
                return yScale(d['y']);
            })
        .attr("r", function(d){if (d.cluster == 0){return 2} else {return 4.5}})
        .style("fill", function(d) { return cluster_colors[cValue(d)];}) 

    no_transforms+=1
    no_prev_points = data.length

}


function add_clustered_points(data){

    xScale.domain([d3.min(data, function(d) { return d['x']; }), d3.max(data, function(d) { return d['x']; })])
    yScale.domain([d3.min(data, function(d) { return d['y']; }), d3.max(data, function(d) { return d['y']; })])

    console.log(data)
    
    svg.selectAll("circle")
        .data(data.slice(0,no_prev_points)) 
        .on("mouseover", mouseover)
        .on("mouseout", mouseout)
        .transition()
        .duration(1000)
        .attr("cx", function(d){
                return xScale(d['x']);
            })
        .attr("cy", function(d){
                return yScale(d['y']);
            })
        .attr("r", function(d){if (d.cluster == 0){return 2} else {return 4.5}})
        .style("fill", function(d) { return cluster_colors[cValue(d)];})

    svg.selectAll("circle")
        .data(data)
        .enter()
        .append("circle")
        .on("mouseover", mouseover)
        .on("mouseout", mouseout)
        .attr("cx", function(d){
            return xScale(d['x']);
        })
        .attr("cy", function(d){
            return yScale(d['y']);
        })
        .attr("r", function(d){if (d.cluster == 0){return 2} else {return 4.5}})
        .style('opacity', 1)
        .style("fill", function(d) { return cluster_colors[cValue(d)];}) 
        .transition()
            .style('fill', '#242424')
            .style('opacity', 0)
        .transition()
            .duration(2000)
            .style("fill", function(d) { return cluster_colors[cValue(d)];}) 
            .style('opacity', 1)

    no_transforms+=1
    no_prev_points = data.length
}

var no_transforms = 0
var no_prev_points = 0
var no_naive_points = 0

var updater = {
    socket: null,

    start: function() {
        updater.socket = new WebSocket('ws://localhost:5000/websocket');
        updater.socket.onmessage = function(event) {
            var newData = JSON.parse(event.data);
            console.log(newData)

            if (newData.type == 'naive' && no_transforms == 0) { 
                if (no_naive_points % 2 == 0){
                    add_naive_point(newData)
                }
                var div = document.getElementById('sidebar');
                div.innerHTML += newData.tweet + "<br>" + "<br>"
                div.scrollTop = div.scrollHeight;
                no_naive_points += 1
            }

            else if (newData.length > 2 && no_transforms == 0){
                first_fix(newData)
            }
        
            else if (newData.length > 2 && no_transforms > 0){
                add_clustered_points(newData)
            }
        
            else{
                var div = document.getElementById('sidebar');
                div.innerHTML += newData.tweet + "<br>" + "<br>"
                div.scrollTop = div.scrollHeight;
            }
        }
    } 
}

// Move nodes toward cluster focus.
function gravity(alpha) {
    return function(d) {
    if ((d.x - d.radius - 2) < rect[0]) d.speedX = Math.abs(d.speedX);
    if ((d.x + d.radius + 2) > rect[2]) d.speedX = -1 * Math.abs(d.speedX);
    if ((d.y - d.radius - 2) < rect[1]) d.speedY = -1 * Math.abs(d.speedY);
    if ((d.y + d.radius + 2) > rect[3]) d.speedY = Math.abs(d.speedY);
     
    d.x = d.x + (d.speedX * alpha);
    d.y = d.y + (-1 * d.speedY * alpha);   
    };
}

// Resolve collisions between nodes.
function collide(alpha) {
    var quadtree = d3.geom.quadtree(nodes);
    return function(d) {
    var r = d.radius + radius.domain()[1] + padding,
    nx1 = d.x - r,
    nx2 = d.x + r,
    ny1 = d.y - r,
    ny2 = d.y + r;
    quadtree.visit(function(quad, x1, y1, x2, y2) {
    if (quad.point && (quad.point !== d)) {
    var x = d.x - quad.point.x,
    y = d.y - quad.point.y,
    l = Math.sqrt(x * x + y * y),
    r = d.radius + quad.point.radius + (d.color !== quad.point.color) * padding;
    if (l < r) {
    l = (l - r) / l * alpha;
    d.x -= x *= l;
    d.y -= y *= l;
    quad.point.x += x;
    quad.point.y += y;
    }
    }
    return x1 > nx2
    || x2 < nx1
    || y1 > ny2
    || y2 < ny1;
    });
    };
    }
