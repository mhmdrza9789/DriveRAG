from typing import List
import logfire


from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings


_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,  
    separators=["\n\n", "\n", " ", ""]
)

def chunk_text(text: str) -> List[str]:
    """
    Splits text into chunks using LangChain's RecursiveCharacterTextSplitter.
    Ensures semantic structure is preserved and limits size.
    """
    with logfire.span("✂️ Text Chunking (LangChain)", text_length=len(text)):
        if not text or not text.strip(): 
            return []
            
        
        chunks = _splitter.split_text(text)
        
        
        valid_chunks = [c.strip() for c in chunks if c.strip()]
        
        logfire.info(f"✅ Generated {len(valid_chunks)} chunks using LangChain")
        return valid_chunks
