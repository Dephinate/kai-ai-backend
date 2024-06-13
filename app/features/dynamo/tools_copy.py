print("inside_tools_copy")
from typing import Any, Dict, List, Optional, Sequence, Union
from enum import Enum
from urllib.parse import parse_qs, urlparse
from langchain_community.document_loaders.base import BaseLoader
# from langchain_community.document_loaders import YoutubeLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate
from langchain_google_vertexai import VertexAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.documents import Document
from langchain.chains.summarize import load_summarize_chain
from langchain_core.pydantic_v1 import BaseModel, Field
from api.error_utilities import VideoTranscriptError
from fastapi import HTTPException
from services.logger import setup_logger
import os


logger = setup_logger(__name__)

# AI Model
model = VertexAI(model="gemini-1.0-pro")

ALLOWED_SCHEMAS = {"http", "https"}
ALLOWED_NETLOCK = {
    "youtu.be",
    "m.youtube.com",
    "youtube.com",
    "www.youtube.com",
    "www.youtube-nocookie.com",
    "vid.plus",
}

class TranscriptFormat(Enum):
    """Transcript format."""

    TEXT = "text"
    LINES = "lines"



def read_text_file(file_path):
    '''
        Reads the contet of any file
    '''
    # Get the directory containing the script file
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Combine the script directory with the relative file path
    absolute_file_path = os.path.join(script_dir, file_path)
    
    with open(absolute_file_path, 'r') as file:
        return file.read()
    
# Parse YouTubeUrl
def parse_video_id(url: str) -> Optional[str]:
        """Parse a youtube url and return the video id if valid, otherwise None."""
        parsed_url = urlparse(url)

        if parsed_url.scheme not in ALLOWED_SCHEMAS:
            return None

        if parsed_url.netloc not in ALLOWED_NETLOCK:
            return None

        path = parsed_url.path

        if path.endswith("/watch"):
            query = parsed_url.query
            parsed_query = parse_qs(query)
            if "v" in parsed_query:
                ids = parsed_query["v"]
                video_id = ids if isinstance(ids, str) else ids[0]
            else:
                return None
        else:
            path = parsed_url.path.lstrip("/")
            video_id = path.split("/")[-1]

        if len(video_id) != 11:  # Video IDs are 11 characters long
            return None

        return video_id

def extract_video_id(youtube_url: str) -> str:
    """Extract video id from common YT urls."""
    print("url inside extract_video: ",youtube_url)
    video_id = parse_video_id(youtube_url)
    if not video_id:
        raise ValueError(
            f"Could not determine the video ID for the URL {youtube_url}"
        )
    return video_id


# Loader with user time-stamps
class YouTubeLoader(BaseLoader):
    def __init__(
        self,
            video_id: str,
            start_time : float = None,
            end_time : float = None,
            add_video_info: bool = False,
            language: Union[str, Sequence[str]] = "en",
            translation: Optional[str] = None,
            transcript_format: TranscriptFormat = TranscriptFormat.TEXT,
            continue_on_failure: bool = False
        
        ):
            """Initialize with YouTube video ID."""
            self.video_id = video_id
            self.start_time = start_time
            self.end_time = end_time
            self.add_video_info = add_video_info
            self.language = language
            if isinstance(language, str):
                self.language = [language]
            else:
                self.language = language
            self.translation = translation
            self.transcript_format = transcript_format
            self.continue_on_failure = continue_on_failure

    def is_within_range(self,d):
        try:
            print("inside is_within_range: ")
            if self.start_time is not None and d['start'] < self.start_time:
                print("False:", self.start_time, d)
                return False
            if self.end_time is not None and d['start'] > self.end_time:
                print("False:", self.start_time, d)

                return False
            print("True:", self.start_time, d)
            
            return True
        except Exception as e:
            print("is_within_range failed")
            raise e


    # Filer transcript text by time stamp
    def filter_dicts_by_time_stamp(self, list_of_dicts):
    # Define the filtering function based on the provided min and/or max values
        print("input to filter transcript: ",self.start_time,self.end_time,list_of_dicts)
        # Apply the filtering function to the list
        return [d for d in list_of_dicts if self.is_within_range(d)]

    def load(self) -> List[Document]:
        """Load documents."""
        try:
            from youtube_transcript_api import (
                NoTranscriptFound,
                TranscriptsDisabled,
                YouTubeTranscriptApi,
            )
        except ImportError:
            raise ImportError(
                "Could not import youtube_transcript_api python package. "
                "Please install it with `pip install youtube-transcript-api`."
            )
        print("inside load_funcion")

        metadata = {"source": self.video_id}

        if self.add_video_info:
            # Get more video meta info
            # Such as title, description, thumbnail url, publish_date
            video_info = self._get_video_info()
            metadata.update(video_info)

        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(self.video_id)
            # print("transcript_language_list: ",transcript_list)
        except TranscriptsDisabled:
            return []

        try:
            transcript = transcript_list.find_transcript(self.language)

        except NoTranscriptFound:
            transcript = transcript_list.find_transcript(["en"])

        if self.translation is not None:
            transcript = transcript.translate(self.translation)

        transcript_pieces = transcript.fetch()
        print("transcript_pieces: ",transcript_pieces)
        
        filetred_transcrpit_peices =[]
        
        # Time Stamp Retrieval
        print("About to filter with start:", self.start_time, "and end:", self.end_time)

        filetred_transcrpit_peices = self.filter_dicts_by_time_stamp(list_of_dicts=transcript_pieces)
        # filetred_transcrpit_peices = self.filter_dicts_by_time_stamp(list_of_dicts=transcript_pieces, start=self.start_time, end=self.end_time)
        print("filetred_transcrpit_peices: ",filetred_transcrpit_peices)
        if self.transcript_format == TranscriptFormat.TEXT:
            transcript = " ".join([t["text"].strip(" ") for t in filetred_transcrpit_peices])
            return [Document(page_content=transcript, metadata=metadata)]
        elif self.transcript_format == TranscriptFormat.LINES:
            return [
                Document(
                    page_content=t["text"].strip(" "),
                    metadata=dict((key, t[key]) for key in t if key != "text"),
                )
                for t in filetred_transcrpit_peices
            ]
        else:
            raise ValueError("Unknown transcript format.")

    def _get_video_info(self) -> dict:
        """Get important video information.

        Components are:
            - title
            - description
            - thumbnail url,
            - publish_date
            - channel_author
            - and more.
        """
        try:
            from pytube import YouTube

        except ImportError:
            raise ImportError(
                "Could not import pytube python package. "
                "Please install it with `pip install pytube`."
            )
        yt = YouTube(f"https://www.youtube.com/watch?v={self.video_id}")
        video_info = {
            "title": yt.title or "Unknown",
            "description": yt.description or "Unknown",
            "view_count": yt.views or 0,
            "thumbnail_url": yt.thumbnail_url or "Unknown",
            "publish_date": yt.publish_date.strftime("%Y-%m-%d %H:%M:%S")
            if yt.publish_date
            else "Unknown",
            "length": yt.length or 0,
            "author": yt.author or "Unknown",
        }
        return video_info

class Summarizer():
    def __init__(self) -> None:
        pass
    
    def summarize_transcript(self, youtube_url: str, start_time: float, end_time: float, max_video_length=600, verbose=False) -> str:
    # def summarize_transcript(youtube_url: str, max_video_length=600, verbose=False) -> str:
        try:
            print("inside summarize_transcript")
            print("url:",youtube_url)
            video_id = extract_video_id(youtube_url=youtube_url)
            print("extracted_video_id: ",video_id)
            print("extracted_start_time: ",start_time)
            print("extracted_end_time: ",end_time)
            loader = YouTubeLoader(video_id=video_id,start_time=start_time, end_time=end_time, add_video_info=True)
            print("loaded_loader")
        except Exception as e:
            logger.error(f"No such video found at {youtube_url}")
            raise VideoTranscriptError(f"No video found", youtube_url) from e
        
        try:
            print("loading docs")
            docs = loader.load()
            print("fetched_docs: ",docs)
            input()
            length = docs[0].metadata["length"]
            title = docs[0].metadata["title"]
        except Exception as e:
            logger.error(f"Video transcript might be private or unavailable in 'en' or the URL is incorrect.")
            raise VideoTranscriptError(f"No video transcripts available", youtube_url) from e
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size = 1000,
            chunk_overlap = 0
        )
        
        split_docs = splitter.split_documents(docs)

        if length > max_video_length:
            raise VideoTranscriptError(f"Video is {length} seconds long, please provide a video less than {max_video_length} seconds long", youtube_url)

        if verbose:
            logger.info(f"Found video with title: {title} and length: {length}")
            logger.info(f"Splitting documents into {len(split_docs)} chunks")
        
        chain = load_summarize_chain(model, chain_type='map_reduce')
        response = chain.invoke(split_docs)
        
        if response and verbose: logger.info("Successfully completed generating summary")
        
        return response['output_text']




    
def generate_flashcards(summary: str, verbose=False) -> list:
    # Receive the summary from the map reduce chain and generate flashcards
    parser = JsonOutputParser(pydantic_object=Flashcard)
    
    if verbose: logger.info(f"Beginning to process summary")
    
    template = read_text_file("prompt/dynamo-prompt.txt")
    examples = read_text_file("prompt/examples.txt")
    
    cards_prompt = PromptTemplate(
        template=template,
        input_variables=["summary", "examples"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
    cards_chain = cards_prompt | model | parser
    
    try:
        response = cards_chain.invoke({"summary": summary, "examples": examples})
    except Exception as e:
        logger.error(f"Failed to generate flashcards: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate flashcards from LLM")
    
    return response

class Flashcard(BaseModel):
    concept: str = Field(description="The concept of the flashcard")
    definition: str = Field(description="The definition of the flashcard")
    
