import json
import umap
import pandas as pd
import time
import ray
import hdbscan
import statistics
from collections import defaultdict, Counter
import math
import spacy 
import preprocessor as p
pd.set_option('display.max_rows', 100)


class helper():

    def __init__(self):
        self.mapper_2d = umap.UMAP(random_state=42,n_neighbors=50)
        self.mapper_100d = umap.UMAP(random_state=42,n_neighbors=50,min_dist=0,n_components=100)
        self.nlp = spacy.load("models/en_core_web_sm-2.2.5", disable=["ner", "parser", "entity_linker", "textcat", "entity_ruler", "sentencizer", "merge_noun_chunks", "merge_entities", "merge_subtokens"])
    
    @ray.remote
    def get_2d_mappings(self, embeddings):
        print('umapping 2d...')
        return self.mapper_2d.fit_transform(embeddings)

    @ray.remote
    def get_100d_mappings(self, embeddings):
        print('umapping 100d...')
        if len(embeddings) < 100:
            return umap.UMAP(random_state=42,n_neighbors=50,min_dist=0,n_components=len(embeddings)-5).fit_transform(embeddings)
        else:
            return self.mapper_100d.fit_transform(embeddings)

    @ray.remote
    def get_clusters(self, df, tweets, mappings):
        print('getting clusters...')
        i = 2
        keep_going = True
        cluster_averages = []
        dataframes = []

        while keep_going == True:
            clusterer = hdbscan.HDBSCAN(min_cluster_size=i)
            clusterer.fit(mappings)

            df_new = pd.DataFrame()
            df_new['tweet'] = tweets
            df_new['x'] = df['x'].values
            df_new['y'] = df['y'].values
            df_new['cluster'] = clusterer.labels_
            df_new['cluster'] = df_new['cluster'].astype(str)
            df_clean = df_new[df_new['cluster'] != '-1']

            cluster_sizes = []
            for cluster, df_cluster in df_clean.groupby('cluster'):
                cluster_sizes.append(len(df_cluster.index))

            try:
                ave_cluster_size = sum(cluster_sizes)/len(cluster_sizes)
            except ZeroDivisionError:
                break

            if len(cluster_averages) > 2:
                mean = sum(cluster_averages)/len(cluster_averages)
                if (ave_cluster_size-mean) > 3 * statistics.stdev(cluster_averages):
                    print('ending search')
                    keep_going = False
                
            cluster_averages.append(ave_cluster_size)
            dataframes.append(df_new)
            i+=1
        
        print('stopped search at:',i)

        if len(dataframes) < 2:
            return dataframes[0]

        else:
            return dataframes[-2]

    
    def get_top_terms(self, df):
        print('getting top terms...')
        word_freq = defaultdict(int)
        freq_by_cluster = defaultdict(defaultdict)

        for cluster, df_c in df.groupby('cluster'):
            tweets = '. '.join([p.clean(tweet) for tweet in df_c['tweet'].values])
            cluster_freq = defaultdict(int)

            doc = self.nlp(tweets)
            for token in doc:
                if token.pos_ in ['ADJ','NOUN','VERB','PROPN'] and len(token.text) > 2:
                    word_freq[token.lemma_.lower()] += 1
                    cluster_freq[token.lemma_.lower()] += 1

            freq_by_cluster[cluster] = cluster_freq

        no_of_words = sum(word_freq.values())

        for k,v in word_freq.items():
            word_freq[k] = v/no_of_words

        for cluster, freq_dict in freq_by_cluster.items():
            no_of_words = sum(freq_dict.values())
            for k,v in freq_dict.items():
                freq_dict[k] = v/no_of_words

        top_terms = defaultdict(str)

        for cluster, freq_dict in freq_by_cluster.items():
            top_words = []
            for k,v in freq_dict.items():
                pW = word_freq[k]
                pWgC = v
                pC = len(freq_dict)/no_of_words
                mi = (pWgC*pC)*math.log((pWgC*pC)/(pW*pC))
                top_words.append((k,mi))
                
            topSorted = sorted(top_words, key=lambda x: x[1],reverse=True)
            top_10 = ', '.join([t[0] for t in topSorted][0:10])
            print(top_10)
            top_terms[cluster] = top_10

        tags = []
        for index, row in df.iterrows():
            tags.append(top_terms[row['cluster']])

        df['top_terms'] = tags
        
        return df
        
    
    @ray.remote
    def get_update(self, tweets, embeddings):
        job1 = self.get_2d_mappings.remote(self, embeddings)
        job2 = self.get_100d_mappings.remote(self, embeddings)

        job_ids = ray.wait([job1, job2], num_returns=2, timeout=None)
        
        mapping_2d = ray.get(job_ids[0][0])
        mapping_100d = ray.get(job_ids[0][1])

        tweets = tweets[0:len(embeddings)]

        df = pd.DataFrame()
        df['tweet'] = tweets
        df['x'] = [p[0] for p in mapping_2d]
        df['y'] = [p[1] for p in mapping_2d]
        df['embedding'] = list(embeddings)

        job = self.get_clusters.remote(self, df, tweets, mapping_100d)
        job_id = ray.wait([job], num_returns=1, timeout=None)
        df_clusters = ray.get(job_id[0][0])

        formatted_cluster = [str(int(c) + 1) for c in df_clusters['cluster'].values]
        del df_clusters['cluster']
        df_clusters['cluster'] = formatted_cluster

        final_df = self.get_top_terms(df_clusters)

        print('job done!')

        return final_df.to_json(orient='records')
        
