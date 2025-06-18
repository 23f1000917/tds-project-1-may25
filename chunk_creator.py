import os 
import time
import filetype
from typing import List, Dict

import requests

from google import genai
from google.genai import types 

from semantic_text_splitter import MarkdownSplitter, TextSplitter



class ChunkCreator:

    chunked_posts   = list() # will contain all posts present in all of the chunks
    chunked_replies = list() # will contain all replies present in all of the chunks
    chunks_contents = list() # will contain contents of all of chunks

    def start_chunk_creation(self, posts, course_content_folder):
        self._from_direct_replies(posts)
        self._from_accepted_answers(posts)
        self._from_topic_level_replies(posts)
        self._from_course_content_markdowns(course_content_folder)
        with open('data/markdowns/raw_chunks.md', 'w', encoding='utf-8') as f:
            f.write('\n\n<!--divider-->\n\n'.join(self.chunks_contents))
        adjusted_chunks = self._split_long_chunks(self.chunks_contents)
        return adjusted_chunks 


    def _from_direct_replies(self, posts: List[Dict], ignore_images=False) -> None:
        # iterate over each post 
        for post in posts:
            # skip if topic starter or no replies 
            if post['post_number'] == 1 or post['reply_count'] == 0: continue

            # get all direct replies 
            replies = self._get_direct_replies( parent=post, posts=posts ) # in posting order

            # create new list for replies ordered by most important to least important
            ordered_replies = list()
            ordered_replies.extend([reply for reply in replies if reply['user_title']]) # faculty replies first
            ordered_replies.extend([reply for reply in replies if not reply['user_title']]) # student replies second

            # create post section
            post_id = '/'.join(post['post_url'].split('/')[-2:])
            post_prefix = f'<original_post|{post_id}>'
            post_content = self._clean_text(post['markdown'])
            post_image_text = '' if ignore_images else self._describe_image(post)
            post_section = f'\n{post_prefix}\n{post_content}\n{post_image_text}\n'
            
            # create replies section 
            replies_section = str()
            for reply in ordered_replies:
                reply_id = '/'.join(reply['post_url'].split('/')[-2:])
                reply_prefix = f'<reply|{reply_id}>'
                reply_content = self._clean_text(reply['markdown'])
                reply_image_text = '' if ignore_images else self._describe_image(reply)
                replies_section +=  f'\n{reply_prefix}\n{reply_content}\n{reply_image_text}\n'
            
            # create complete chunk containing post + replies
            chunk_content = (post_section + replies_section).strip()
            # keep track of all the chunked components
            self.chunked_posts.append(post)
            self.chunked_replies.extend(ordered_replies)
            self.chunks_contents.append(chunk_content)
            print(f'chunk for {post_prefix} created!')
            

    def _from_accepted_answers(self, posts: List, ignore_images=False) -> None:
        # iterate over each post
        for post in posts:
            # skip if post is not a topic starter 
            if post['post_number'] > 1: continue
            # find accepted answer
            accepted_reply = self._get_accepted_answer(topic_starter=post, posts=posts)
            # skip if no accepted answer 
            if not accepted_reply: continue

            # create post section
            post_id = '/'.join(post['post_url'].split('/')[-2:])
            post_prefix = f'<original_post|{post_id}>'
            post_content = self._clean_text(post['markdown'])
            post_image_text = '' if ignore_images else self._describe_image(post)
            post_section = f'\n{post_prefix}\n{post_content}\n{post_image_text}\n'

            # create accepted reply secion 
            reply_id = '/'.join(accepted_reply['post_url'].split('/')[-2:])
            reply_prefix = f'<reply|{reply_id}>'
            reply_content = self._clean_text(accepted_reply['markdown'])
            reply_image_text = '' if ignore_images else self._describe_image(accepted_reply)
            reply_section =  f'\n{reply_prefix}\n{reply_content}\n{reply_image_text}\n'

            # create complete chunk containing post + accepted reply
            chunk_content = (post_section + reply_section).strip()
            # keep track of all the chunked components
            self.chunked_posts.append(post)
            self.chunked_replies.append(accepted_reply)
            self.chunks_contents.append(chunk_content)
            print(f'chunk for {post_prefix} created!')


    def _from_topic_level_replies(self, posts: List[Dict], ignore_images=False):
        # iterate over each post 
        for post in posts:
            # skip if not a topic starter 
            if post['post_number'] > 1: continue 
            # skip if post already chunked 
            if post in self.chunked_posts: continue
            # get all replies to the topic starter 
            replies = self._get_top_level_replies(parent=post, posts=posts)
            # filter out unchunked replies 
            unchunked_replies = [r for r in replies if r not in self.chunked_posts + self.chunked_replies]

            # create post section
            post_id = '/'.join(post['post_url'].split('/')[-2:])
            post_prefix = f'<original_post|{post_id}>'
            post_content = self._clean_text(post['markdown'])
            post_image_text = '' if ignore_images else self._describe_image(post)
            post_section = f'\n{post_prefix}\n{post_content}\n{post_image_text}\n'
            
            # create replies section 
            replies_section = str()
            for reply in unchunked_replies:
                reply_id = '/'.join(reply['post_url'].split('/')[-2:])
                reply_prefix = f'<reply|{reply_id}>'
                reply_content = self._clean_text(reply['markdown'])
                reply_image_text = '' if ignore_images else self._describe_image(reply)
                replies_section +=  f'\n{reply_prefix}\n{reply_content}\n{reply_image_text}\n'
            
            # create complete chunk containing post + replies
            chunk_content = (post_section + replies_section).strip()
            # keep track of all the chunked components
            self.chunked_posts.append(post)
            self.chunked_replies.extend(unchunked_replies)
            self.chunks_contents.append(chunk_content)
            print(f'chunk for {post_prefix} created!')


    def _from_course_content_markdowns(self, folder_path):
        # create markdown file paths list 
        filenames = sorted(os.listdir(folder_path))
        filepaths = [f'{folder_path}/{filename}' for filename in filenames]

        # markdown splitter to create chunks
        splitter = MarkdownSplitter(capacity=1000, overlap=200)
        
        # iterate over each file path 
        for filepath in filepaths:
            # section source 
            source = filepath.split('/')[-1].removesuffix('.md')

            # section content from markdown file
            f = open(filepath, 'r', encoding='utf-8')
            markdown_text = f.read()
            f.close()

            # create splits 
            splits = splitter.chunks(markdown_text)
            
            # prefix source to every split and append to chunks.md
            source_prefix = f'<course-content|{source}>'
            for split in splits:
                split_content = f'{source_prefix}\n{split}'
                # appent to chunk_contents
                self.chunks_contents.append(split_content)
            print(f'chunks for {source_prefix} created!')
            

                

    def _split_long_chunks(self, chunks_contents):
        # create empty list to hold splitted chunks
        adjusted_chunks = list()
        # iterate over content of each created chunk
        for chunk_content in chunks_contents:
            # make no changes if small length
            if len(chunk_content) < 2000: 
                adjusted_chunks.append(chunk_content)
                continue

            # split the chunk further 
            sections = chunk_content.split('\n')
            source_prefix = sections[0]
            content_section = '\n'.join(sections[1:])
            splitter = TextSplitter(capacity=2000, overlap=500)
            splits = splitter.chunks(content_section)
            # append split to adjusted chunks
            adjusted_length = 0
            for split in splits:
                adjusted_length += len(split)
                split_content = f'{source_prefix}\n{split}'
                adjusted_chunks.append(split_content)
        return adjusted_chunks


    def _get_direct_replies(self, parent: Dict, posts: List[Dict]) -> List[Dict]:
        return [ # replies to non-topic-starters
            post for post in posts if post != parent 
            and post['topic_title'] == parent['topic_title'] 
            and post['reply_to_post_number'] == parent['post_number']
        ]

    def _get_accepted_answer(self, topic_starter: Dict, posts: List[Dict]):
        return next(( # reply under a topic-start that has been accepted as solution
            post for post in posts if post['accepted_answer']
            and post['topic_title'] == topic_starter['topic_title']
        ), None)


    def _get_top_level_replies(self, parent: Dict, posts: List[Dict]):
        return [ # all of the replies under a topic-starter
            post for post in posts if post != parent
            and post['topic_title'] == parent['topic_title']
        ]
    
    def _describe_image(self, post: Dict) -> str:

        if not post['image_urls']:
            return ''

        text_prompt = (
            'I am building an AI assistant that answers student queries based on forum data. '
            'I will convert the images posted by users in the forum to their textual descriptions. '
            'These descriptions will be embedded so that they can be used for RAG.'
            'When the assistant receives an image in the student query, it will also be converted to '
            'its textual description and then to its embedding. '
            'I have attached the image in the prompt. '
            'You are supposed to give a detailed description of the image, the image might be a '
            'part of a user question or an answer by a user to some question. Try to find out what '
            'is being conveyed through the image and any text that the user has provided along with it. '
            'IMPORTANT NOTE: If you think the image is some sort of a meme, joke, or something not related to studies, '
            'reply with a simple "no useful information", and nothing else. '
            'The description must not exceed 4-5 sentences.'
            f'Text content in the user post: { post['markdown'].strip() if post['markdown'] else 'None' }'
        )

        client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))
        image_prompts = []
        for img_url in post['image_urls']:
            img_bytes = requests.get(img_url).content
            mime = filetype.guess_mime(img_bytes)
            part = types.Part.from_bytes(data=img_bytes, mime_type=mime)  # type: ignore
            image_prompts.append(part)

        prompt_contents = [text_prompt] + image_prompts
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash-lite',
                contents = prompt_contents
            )
            time.sleep(0.5)
            return 'Image Description: \n' + response.text + '\n' # type: ignore
        except:
            print( f'Description could not be created for image in {post['post_url']}')
            return ''
    
    

    def _clean_text(self, markdown: str)-> str:
        replace = {'\n\n\n': '\n', '\n\n' : '\n'}
        for key, value in replace.items():
            markdown = markdown.replace(key, value)
        return markdown.strip()

            
        