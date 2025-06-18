import os 
import json
import numpy as np

from embed_gen import Embedder
from chunk_creator import ChunkCreator
from solution_creator import SolutionCreator
from discourse_scraper import DiscourseScraper

# Initialize discourse scraper with course id of TDS (34)
discourse_scraper = DiscourseScraper(category_id=34) # 

# scrape the posts if 'posts.json' does not exist
if not os.path.exists('data/json/posts.json'):  # TDS course has ID-34 
    discourse_scraper.scrape_forum(start_date_str="2025-01-01", end_date_str="2025-04-14")
# else load the posts from storage
else:
    with open('data/json/posts.json', 'r', encoding='utf-8') as file:
        posts = json.load(file)
    print('posts.json loaded!')


# chunk creation
chunk_creator = ChunkCreator()
if not os.path.exists('data/json/chunks.json'):
    print('creating chunks...')

    chunks = chunk_creator.start_chunk_creation(posts, 'data/markdowns/course_content')

    with open('data/json/chunks.json', 'w', encoding='utf-8') as f:

        json.dump(chunks, f, indent=4)

    print('chunks.json created!')
else:
    with open('data/json/chunks.json', 'r', encoding='utf-8') as file:
        chunks = json.load(file)
    print('chunks.json loaded!')
    print('total chunks: ', len(chunks))

# embedding generation 
embedder = Embedder()
if not os.path.exists('embed_data.npz'):
    print('generating embeddings...')

    embedder.create_chunk_embeddings(chunks)

    print('embeddings created!')

else:
    embed_data = np.load('embed_data.npz')
    print('embed_data.npz loaded!')

    embeddings = embed_data['embeddings']
    sources = embed_data['sources']