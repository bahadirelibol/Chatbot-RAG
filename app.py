import os
import json
import time
import io
import base64
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

# Ekstra kütüphaneler: Ses tanıma ve sesli cevap
import speech_recognition as sr
from gtts import gTTS

# Kalıcı sohbet geçmişi için dosya yolu
HISTORY_FILE = "chat_history.json"

def load_chat_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {"conversations": []}
    else:
        return {"conversations": []}

def save_chat_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def record_voice():
    """Mikrofon üzerinden ses kaydı alıp, sesi metne dönüştürür."""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("Dinliyorum... Lütfen konuşun.")
        audio = r.listen(source)
    try:
        text = r.recognize_google(audio, language="tr-TR")
        st.success("Ses tanımlandı: " + text)
        return text
    except Exception as e:
        st.error("Ses tanıma başarısız oldu: " + str(e))
        return None

def speak_text(text):
    """Metni sesli yanıt olarak otomatik oynatır."""
    tts = gTTS(text=text, lang='tr')
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    audio_bytes = fp.getvalue()
    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
    audio_html = f'''
    <audio controls autoplay style="display:none;">
        <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
    </audio>
    '''
    st.markdown(audio_html, unsafe_allow_html=True)

load_dotenv()

st.title("Basketbol Kuralları CHATBOT 🏀")

# Oturum başlangıcında sohbet geçmişini JSON dosyasından yüklüyoruz
if "chat_history" not in st.session_state:
    st.session_state.chat_history = load_chat_history()

# Eğer daha önce hiç sohbet oluşturulmamışsa, yeni bir sohbet oluşturuyoruz.
if "current_chat_id" not in st.session_state:
    if st.session_state.chat_history["conversations"]:
        st.session_state.current_chat_id = st.session_state.chat_history["conversations"][0]["id"]
    else:
        new_id = str(int(time.time()))
        new_chat = {"id": new_id, "name": f"Chat {new_id}", "messages": []}
        st.session_state.chat_history["conversations"].append(new_chat)
        st.session_state.current_chat_id = new_id
        save_chat_history(st.session_state.chat_history)

# Sidebar: Mevcut sohbetleri listeleyip seçim yapılmasını sağlıyoruz.
chat_options = {chat["name"]: chat["id"] for chat in st.session_state.chat_history["conversations"]}
selected_chat_name = st.sidebar.selectbox("Geçmiş Sohbetler", list(chat_options.keys()))
selected_chat_id = chat_options[selected_chat_name]

if selected_chat_id != st.session_state.current_chat_id:
    st.session_state.current_chat_id = selected_chat_id

# Sidebar'da yeni sohbet oluşturmak için isim girme alanı
new_chat_name = st.sidebar.text_input("Yeni sohbet adı (isteğe bağlı)", "")
if st.sidebar.button("Yeni Chat Başlat"):
    new_id = str(int(time.time()))
    chat_name = new_chat_name if new_chat_name.strip() != "" else f"Chat {new_id}"
    new_chat = {"id": new_id, "name": chat_name, "messages": []}
    st.session_state.chat_history["conversations"].append(new_chat)
    st.session_state.current_chat_id = new_id
    save_chat_history(st.session_state.chat_history)

if st.sidebar.button("Sohbeti Sil"):
    st.session_state.chat_history["conversations"] = [
        chat for chat in st.session_state.chat_history["conversations"]
        if chat["id"] != st.session_state.current_chat_id
    ]
    if not st.session_state.chat_history["conversations"]:
        new_id = str(int(time.time()))
        new_chat = {"id": new_id, "name": f"Chat {new_id}", "messages": []}
        st.session_state.chat_history["conversations"].append(new_chat)
        st.session_state.current_chat_id = new_id
    else:
        st.session_state.current_chat_id = st.session_state.chat_history["conversations"][0]["id"]
    save_chat_history(st.session_state.chat_history)

# Seçilen sohbetin mesajlarını alıyoruz.
current_chat = next(
    (chat for chat in st.session_state.chat_history["conversations"] 
     if chat["id"] == st.session_state.current_chat_id),
    {"id": st.session_state.current_chat_id, "name": "Yeni Chat", "messages": []}
)

# Chat mesajlarını görüntülemek için container ve render fonksiyonu
chat_container = st.container()

def render_chat():
    chat_container.empty()
    with chat_container:
        for msg in current_chat["messages"]:
            if msg["role"] == "user":
                st.chat_message("user").write(msg["content"])
            else:
                st.chat_message("assistant").write(msg["content"])

# İlk render: Mevcut sohbet geçmişi gösteriliyor.
render_chat()

# Sesli sorgu butonu: Kullanıcı sesli soru sorduğunda, mesaj eklenir ve sohbet ekranı güncellenir.
voice_query = None
if st.button("Sesli Soru Sor", key="voice_btn"):
    voice_query = record_voice()
    if voice_query:
        # Aynı mesajı tekrar eklememek için kontrol
        if not any(msg["content"] == voice_query for msg in current_chat["messages"]):
            current_chat["messages"].append({"role": "user", "content": voice_query})
            save_chat_history(st.session_state.chat_history)
            render_chat()

# Metin girişi: Her zaman görünür durumda.
text_query = st.chat_input("Bir şeyler sor veya yaz:")

# Sorgu belirleme: Yazılı sorguya öncelik veriliyor.
if text_query:
    query = text_query
    query_source = "text"
elif voice_query:
    query = voice_query
    query_source = "voice"
else:
    query = None
    query_source = None

if query:
    # Eğer sorgu henüz eklenmediyse, ekliyoruz (yazılı sorgu için).
    if query_source == "text" and not any(msg["content"] == query for msg in current_chat["messages"]):
        current_chat["messages"].append({"role": "user", "content": query})
        save_chat_history(st.session_state.chat_history)
        render_chat()

    # PDF'den veri yükleme ve chatbot ayarları
    loader = PyPDFLoader("basketbol_kural.pdf")
    data = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000)
    docs = text_splitter.split_documents(data)

    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vectorstore = Chroma.from_documents(documents=docs, embedding=embeddings, persist_directory="./chroma_db")
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 10})

    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro",
        temperature=0.3,
        max_tokens=500
    )

    system_prompt = (
        "Sen bir yardımcı asistansın ve yalnızca basketbol kuralları hakkında sorulara cevap veriyorsun. "
        "Yanıtlarını yalnızca verilen bağlam içeriğinden oluştur. "
        "Eğer sorunun cevabını bilmiyorsan, 'Bu konuda yardımcı olamıyorum.' de. "
        "Cevaplarını en fazla üç cümle ile ver ve doğru bilgi içerdiğinden emin ol.\n\n"
        "{context}"
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}")
        ]
    )

    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    response = rag_chain.invoke({"input": query})

    # Bot cevabını ekliyoruz
    current_chat["messages"].append({"role": "assistant", "content": response["answer"]})
    save_chat_history(st.session_state.chat_history)
    render_chat()

    # Sadece sesli sorgu durumunda sesli oynatma
    if query_source == "voice":
        speak_text(response["answer"])
