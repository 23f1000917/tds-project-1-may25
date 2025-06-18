import json
import base64
import filetype
import numpy as np 


from google import genai
from google.genai import types

from embed_gen import Embedder



class SolutionCreator():
    def create_solution(self, query):

        print('creating solution...') # report process

        # get query text
        query_text = query.get('question')

        if not query_text:
            query_text = ""
        
        # get query image (optional)
        query_image_b64 = query.get('image')

        # image_description will be appended to student question to create a single embedding
        # image_prompts list will be directly sent to gemini later to craft answers along with the chunk texts
        image_description, image_prompts = self._get_image_description(query_image_b64, query_text)

        # complete query content 
        query_content = query_text + image_description

        # get indices and sources of top 5 most similar chunks based on cosine similarity 

        print('embedding user query...')
        embedder = Embedder()
        query_embedding = embedder.embed_content(query_content)

        # search through embedding database 

        print('searching through the embedded data...')
        top_indices, top_sources = self._get_most_similar_indices(query_embedding)

        # get context for gemini prompt
        gemini_context = self._format_context_for_gemini(top_indices)

        # get answer from gemini
        answer = self._get_answer_from_gemini(query_content, gemini_context, image_prompts)

        # create 'context_links' list containign source_url and text
        context_links = self._create_context_links(top_sources)

        print(answer)

        return dict(
            answer = answer,
            links = context_links
        )


    
    def _get_answer_from_gemini(self, query_content, gemini_context, image_prompts):

        print('crafting an answer...')

        text_prompt = (
            "You are a Retrieval-Augmented Generation (RAG) assistant. "
            "You've been provided with context snippets from an online forum that belongs to an educational institution. "
            "Your purpose is to answer student queries based on the context. \n\n"
            "IMPORTANT NOTES:\n"
            "1. Context snippets may be:\n"
            " - Fragmented or incomplete\n"
            " - Contain typos or formatting issues \n"
            " - Include URLs that are valid references \n"
            " - Contain redundant information \n"
            " - Contain *textual* description of any image present in the actual forum post \n"
            " - Scan the context snippets properly, do not respond with made up information. \n"
            " - If you can't find some information in the context, respond with 'I don't know'\n"
            "2. A student can upload images with their query that: \n"
            " - Contain the actual question \n"
            " - Provide visual context for the question \n"
            " - Show information not in text snippets \n"
            " - Images present in the student query will be attached with the prompt \n"
            "3. The user query text might be incomplete without images \n"
        
            f"\nSTUDENT QUERY TEXT:\n{query_content} \n\n"
            f"\nCONTEXT SNIPPETS:\n{gemini_context}"
        )

        prompt_contents = [text_prompt]

        if image_prompts:
            prompt_contents.extend(image_prompts)

        client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents = prompt_contents
        )
        return response.text

        

    def _create_context_links(self, top_sources):

        source_urls = list()

        for source_str in top_sources:
            source_list = source_str.split('|')
            source_urls.extend([url for url in source_list if url not in source_urls])

        # preload the posts list 
        with open('data/json/posts.json', 'r', encoding='utf-8') as f:
            posts = json.load(f)

        # context_links will be a list of dicts containing url and text
        context_links = []

        for source_url in source_urls:
            if 'discourse.onlinedegree.iitm.ac.in' in source_url:
                source_id = '/'.join(source_url.split('/')[-2:])
                for post in posts:
                    post_id = '/'.join(post['post_url'].split('/')[-2:])
                    if source_id == post_id:
                        context_links.append(dict(
                            url = source_url,
                            text = post['markdown']
                        ))
                
            elif 'tds.s-anand.net' in source_url:
                source_id = source_url.split('/')[-1]
                filepath = f'data/markdowns/course_content/{source_id}.md'
                with open(filepath, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                context_links.append(dict(
                    url = source_url,
                    text = file_content
                ))

        return context_links
        

        

    def _format_context_for_gemini(self, top_indices):

        with open('data/json/chunks.json', 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        context_snippets = list()
        for index in top_indices:
            context_snippets.append(chunks[index])

        return '\n\n\n'.join(context_snippets)



    def _get_most_similar_indices(self, query_embedding, k=10):

        # load embeddings 
        embed_data = np.load('embed_data.npz')
        embeddings = embed_data['embeddings']
        sources = embed_data['sources']

        # Ensure query_embedding is 2D (1, n_features) for dot product
        query_embedding = np.array(query_embedding)
        query_embedding = query_embedding.reshape(1, -1)
        
        # Compute cosine similarity manually:
        # 1. Dot product between query and embeddings (numerator)
        dot_product = np.dot(embeddings, query_embedding.T).flatten()
        
        # 2. Norm of embeddings and query (denominator)
        embeddings_norm = np.linalg.norm(embeddings, axis=1)
        query_norm = np.linalg.norm(query_embedding)
        
        # 3. Cosine similarity = dot_product / (norm(embeddings) * norm(query))
        cosine_similarities = dot_product / (embeddings_norm * query_norm)
        
        # Get indices of top k similarities (descending order)
        top_k_indices = np.argsort(cosine_similarities)[-k:][::-1]
        top_k_sources = sources[top_k_indices]

        return top_k_indices, top_k_sources


        
    def _get_image_description(self, query_image, query_text):
        # return empty string if no image passed in user query
        if not query_image:
            return '', []

        # create list of b64 codes of query images
        if isinstance(query_image, str):
            images_b64 = [query_image]

        elif isinstance(query_image, list):
            images_b64 = query_image
        
        # create list of decoded image bytes
        decoded_images = list()
        for img_b64 in images_b64:
            image_bytes = base64.b64decode(img_b64)
            decoded_images.append(image_bytes)

        
        # create text prompt for gemini
        text_prompt = (
            'I have built an AI assistant that answers student queries based on online forum posts. '
            'I have decided that if a student query contains an image, it will be converted to its '
            'textual description. This description will be embedded along with the query text for '
            'RAG. The online forum data has already been embedded. Your task is to write a textual '
            'description of the image in the student query. Use the query text sent along with it to find '
            'exactly what is being asked by the student. Give a detailed description of any possible ' 
            'question in the image, or any other message that is being conveyed. The description ' 
            'should not exceed 4-5 sentences. \n\n'
            'Below is the text content present in the student query:\n\n'
            f'{query_text if query_text else 'No Text Provided.'}'
        )
        # append text prompt to prompt contents

        image_prompts = list()

        # create image prompts 
        for image_bytes in decoded_images:
            mime = filetype.guess_mime(image_bytes)
            part = types.Part.from_bytes(data=image_bytes, mime_type=mime) # type: ignore
            image_prompts.append(part)
        
        prompt_contents = [text_prompt] + image_prompts

        # get response from gemini
        try:
            client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))
            response = client.models.generate_content(
                model='gemini-2.0-flash-lite',
                contents = prompt_contents
            )
            image_description = f'Image Description:\n{response.text}'
            return image_description, image_prompts
        except:
            return '', []
        
