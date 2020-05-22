import tornado.ioloop
import tornado.escape
import tornado.web
import tornado.websocket
import logging
from tornado.options import options
import os
import numpy as np
import json 
import preprocessor as p
from sentence_transformers.SentenceTransformer import SentenceTransformer
import datetime
import time
import tweepy
from tweepy import Stream
from urllib3.exceptions import ProtocolError
import asyncio
from tornado.platform.asyncio import AnyThreadEventLoopPolicy
from helpers import helper
import ray


ray.init(webui_host='127.0.0.1')

consumer_key = 'UJDkiKujryTSYjQvi10aYXv5n'
consumer_secret = '7v1M3393cZolOO9zA5xxdBk5GsOLQrdCOflyOKvo0mzHwFxsZo'
access_token = '148209733-gufAZsqHsSImDiQKAr0RVdcdQLd0CZEdQY1hRfkC'
access_token_secret = 'MdGK5fhz5teqJPFXr7BHw9fmdWQDibVGsXJ7YOsO3EcWp'

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [(r"/", MainHandler), (r"/websocket", TweetHandler)]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
        )
        super(Application, self).__init__(handlers, **settings)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")


class TweetHandler(tornado.websocket.WebSocketHandler):

    waiters = []
    tweet_bank = []
    embedding_bank = []
    first_job_done = False

    def open(self):
        TweetHandler.waiters.append(self)

    def on_message(self, message):
        parsed = json.loads(message)
        self.handler(parsed['body'])

    def handler(self, search_term):
        while True:
            try:
                twitterStream = Stream(auth, tweetStreamer())
                twitterStream.filter(languages=["en"],track=[search_term], is_async=True)

                time.sleep(10)
                
                if self.first_job_done == False:
                    self.job = helper.get_update.remote(helper, self.tweet_bank, self.embedding_bank)
                    self.first_job_done = True

                else:
                    ids = ray.wait([self.job], num_returns=1, timeout=None)
                    to_send = ray.get(ids[0][0])  
                    self.waiters[0].write_message(to_send)
                    self.job = helper.get_update.remote(helper, self.tweet_bank, self.embedding_bank)

                twitterStream.disconnect()               

            except (ProtocolError, AttributeError):
                continue   


class tweetStreamer(tweepy.StreamListener):  

    def cleanup(self,tweet):
        p.set_options(p.OPT.URL, p.OPT.EMOJI, p.OPT.RESERVED, p.OPT.SMILEY)
        p.clean(tweet)
        return p.clean(tweet)

    def extract_tweet(self,tweet_dict):
        tweet = ''
        if 'retweeted_status' in tweet_dict.keys():
            try:
                tweet = tweet_dict['retweeted_status']['extended_tweet']['full_text']
            except KeyError:
                tweet = tweet_dict['retweeted_status']['text']
        if 'extended_tweet' in tweet_dict.keys():
            tweet = tweet_dict['extended_tweet']['full_text']
        if tweet == '':
            tweet = tweet_dict['text']
        return self.cleanup(tweet)

    def get_naive_point(self, tweet):
        to_send = {'tweet': tweet,
                   'type': 'naive',
                   'cluster': "none",
                   'x': 0,
                   'y': 0}
        return json.dumps(to_send)

    def on_status(self, status):
        tweet = self.extract_tweet(status._json)
        TweetHandler.tweet_bank.append(tweet)
        if len(TweetHandler.tweet_bank) > 1000:
            TweetHandler.tweet_bank.pop(0)

        embedding = model.encode([tweet])
        TweetHandler.embedding_bank.append(np.array(embedding[0]))
        if len(TweetHandler.embedding_bank) > 1000:
            TweetHandler.embedding_bank.pop(0)

        data = self.get_naive_point(tweet)

        logging.info("tweet: %d", tweet)

        for waiter in TweetHandler.waiters:
            waiter.write_message(data)


if __name__ == "__main__":
    model = SentenceTransformer('models/roberta-base-nli-stsb-mean-tokens')
    asyncio.set_event_loop_policy(AnyThreadEventLoopPolicy())
    app = Application()
    helper = helper()
    app.listen(5000)

    print('initializing...')
    
    initializers = np.load('initializers.npy',allow_pickle=True)
    warmup = helper.get_update.remote(helper, ['test']*105, initializers)
    ray.wait([warmup],num_returns=1,timeout=None)
    
    print('ready!')
    
    tornado.ioloop.IOLoop.current().start()
    
