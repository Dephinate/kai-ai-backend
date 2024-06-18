print("inside core")

from features.dynamo.tools_copy import generate_flashcards
from features.dynamo.tools_copy import Summarizer

print("still inside core")
from services.logger import setup_logger
from api.error_utilities import VideoTranscriptError

logger = setup_logger(__name__)

# def executor(youtube_url: str, verbose=False):
#     summary = summarize_transcript(youtube_url, verbose=verbose)
#     flashcards = generate_flashcards(summary)

#     sanitized_flashcards = []
#     for flashcard in flashcards:
#         if 'concept' in flashcard and 'definition' in flashcard:
#             sanitized_flashcards.append({
#                 "concept": flashcard['concept'],
#                 "definition": flashcard['definition']
#             })
#         else:
#             logger.warning(f"Malformed flashcard skipped: {flashcard}")

#     return sanitized_flashcards 


def executor(**input_dict):
    summarizer  = Summarizer()
    print("loaded_summarizer")
    print("input_to_executor: ",input_dict)
    # input()

    input_transcript = {
        "youtube_url" : input_dict.get("youtube_url",None),
        "start_time" : input_dict.get("start_time",None),
        "end_time" : input_dict.get("end_time",None)
    }
    input_files = input_dict.get("files",None)

    print("input_for_transcript: ",input_transcript)
    print("input_for_files: ", input_files)
    # input()



    if input_transcript["youtube_url"] is not None:
        summary = summarizer.summarize_transcript(verbose=True,**input_transcript)
        print("summary: ",summary)
        input()
        flashcards = generate_flashcards(summary)
        sanitized_flashcards = []
        for flashcard in flashcards:
            if 'concept' in flashcard and 'definition' in flashcard:
                sanitized_flashcards.append({
                    "concept": flashcard['concept'],
                    "definition": flashcard['definition']
                })
            else:
                logger.warning(f"Malformed flashcard skipped: {flashcard}")

        return sanitized_flashcards 