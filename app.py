import streamlit as st
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain

load_dotenv()

st.title("T.C. ANAYASA CHATBOT")

loader = PyPDFLoader("Anayasa.pdf")
data = loader.load()

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000)
docs = text_splitter.split_documents(data)

embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
vectorstore = Chroma.from_documents(documents=docs,embedding=embeddings,persist_directory="./chroma_db")

retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs= {"k" : 10})

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",
    temperature=0.3,
    max_tokens=500
)

query=st.chat_input("Bir şeyler sor veya yaz:")
prompt = query

system_prompt = (
    "Sen bir yardımcı asistansın ve yalnızca T.C. anayasası ve anayasa maddeleri hakkında sorulara cevap veriyorsun. "
    "Yanıtlarını yalnızca verilen bağlam içeriğinden oluştur. "
    "Eğer sorunun cevabını bilmiyorsan, 'Bu konuda yardımcı olamıyorum.' de. "
    "Cevaplarını en fazla üç cümle ile ver ve doğru bilgi içerdiğinden emin ol.\n\n"
    "{context}"
)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system",system_prompt),
        ("human","{input}")
    ]
)

if query:
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    response = rag_chain.invoke({"input": query})  # Kullanıcının girdisini kullan
    
    st.write(response["answer"])
