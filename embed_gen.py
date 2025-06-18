import re
import json
import time  
import requests
import numpy as np


class Embedder:

    def create_chunk_embeddings(self, chunks_contents):
        # elements at the ith index will correspond to the ith chunk
        sources = [] # nested list containing source URLs for each chunk
        embeddings = [] # will contain embeddings for each chunk content

        for index, chunk_content in enumerate(chunks_contents):
            # extract source url
            source_url = self._get_source_urls(chunk_content)
            embed_vector = []
            try:
                # create embedding
                embed_vector = self.embed_content(chunk_content)
            except: # in case of any error
                print(f'ERROR generating embedding for chunk at index {index}')
                # save the sucessfully created embeddings
                np.savez(
                    f'embed_data_{index - 1}.npz', # contains last successful chunk_index
                    sources = np.array(sources),
                    embeddings = np.array(embeddings)
                )
                return 
            # append
            sources.append(source_url)
            embeddings.append(embed_vector)
            print(f'embedding generated for chunk at index {index}') # report progress

            time.sleep(1) # for rate limit of embedding model

        # save all embeddings if loop succesfully completed 
        np.savez(
            'embed_data.npz',
            sources = np.array(sources),
            embeddings = np.array(embeddings)
        )
        return 
    

    def embed_content(self, content):
        URL = 'https://aipipe.org/openai/v1/embeddings'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {os.environ.get('AIPIPE_KEY')}'
        }
        data = {
            "model": "text-embedding-3-small",
            "input": content
        }
        response = requests.post(URL, headers=headers, data=json.dumps(data))
        embedding = response.json()['data'][0]['embedding']
        return embedding
    


    def _get_source_urls(self, chunk_content):
        # discourse url
        DISCOURSE_URL = 'https://discourse.onlinedegree.iitm.ac.in'
        
        # course content url
        CC_URL = 'https://tds.s-anand.net/#/'


        # find all source IDs
        pattern = r'<[^|]+\|[^>]+>'
        sources = re.findall(pattern, chunk_content)

        # will contain all source urls for the chunk
        source_urls = list()

        for source in sources:
            if 'original_post' in source:
                source_id = source.split('|')[1].removesuffix('>')
                source_url = f'{DISCOURSE_URL}/t/{source_id}'
                source_urls.append(source_url)

            elif 'reply' in source:
                source_id = source.split('|')[1].removesuffix('>')
                source_url = f'{DISCOURSE_URL}/t/{source_id}'
                source_urls.append(source_url)
            
            elif 'course-content' in source:
                source_id = source.split('|')[1].removesuffix('>')
                source_url = f'{CC_URL}{source_id}'
                source_urls.append(source_url)
        
        return '|'.join(source_urls) # join the urls by '|' in a single string
    



    

