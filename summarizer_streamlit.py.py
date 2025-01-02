import streamlit as st
from transformers import pipeline

def summarize_article(article_text, max_length=150, min_length=50):
    """
    Summarizes a given article using a pre-trained model.
    
    Args:
        article_text (str): The article text to summarize.
        max_length (int): Maximum length of the summary.
        min_length (int): Minimum length of the summary.
        
    Returns:
        str: The summary of the article.
    """
    try:
        summarizer = pipeline("summarization")
        summary = summarizer(article_text, max_length=max_length, min_length=min_length, do_sample=False)
        return summary[0]['summary_text']
    except Exception as e:
        return f"Error during summarization: {e}"

# Streamlit UI for user input
st.title("AI Article Summarizer")
st.write("Enter an article below and get a concise summary.")

# User input (text area for long articles)
article_text = st.text_area("Article Text", height=300)

if st.button("Generate Summary"):
    if article_text:
        summary = summarize_article(article_text)
        st.subheader("Summary:")
        st.write(summary)
    else:
        st.warning("Please enter an article to summarize.")
