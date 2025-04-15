# çalıştırmak için : uvicorn main:app --reload 

# Kütüphanelerin İçeri Aktarılması
import time
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from dotenv import load_dotenv
from typing import Optional, List, Dict 
import os
import json
import uuid
import datetime
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

# Çevre değişkenlerini yükleme
load_dotenv()

# FastAPI Uygulamasını Başlatma
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
llm = None  # Global LLM değişkeni
SESSIONS_FILE = "chat_history.json"

# API key kontrolü
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY bulunamadı!")

print(f"API Key yüklendi: {api_key[:10]}...")

# Global değişkenler
vectorstore = None

# LLM Modelini Başlatma
def initialize_model():
    global llm
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            google_api_key=api_key,
            temperature=0.3,
            convert_system_message_to_human=True,
            max_output_tokens=500
        )
        # Test mesajı
        test_response = llm.invoke("Test mesajı")
        print("✅ Gemini 1.5 Pro başarıyla yüklendi!")
        return True
    except Exception as e:
        print(f"❌ Model yükleme hatası: {e}")
        return False

# PDF yükleme ve vektör veritabanı oluşturma
def initialize_vectorstore():
    global vectorstore
    try:
        loader = PyPDFLoader("basketbol_kural.pdf")
        data = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000)
        docs = text_splitter.split_documents(data)
        
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        vectorstore = Chroma.from_documents(
            documents=docs, 
            embedding=embeddings, 
            persist_directory="./chroma_db"
        )
        print("✅ PDF başarıyla yüklendi ve vektör veritabanı oluşturuldu!")
    except Exception as e:
        print(f"❌ PDF yükleme hatası: {e}")

#AI Modelinden Yanıt Alma
def get_ai_response(question: str) -> str:
    try:
        if llm is None:
            return "Model henüz yüklenmedi. Lütfen daha sonra tekrar deneyin."
        
        if vectorstore is None:
            return "PDF veritabanı henüz yüklenmedi. Lütfen daha sonra tekrar deneyin."

        # Benzer içerikleri getir
        retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 5})
        docs = retriever.get_relevant_documents(question)
        context = "\n".join([doc.page_content for doc in docs])

        system_prompt = ("Sen bir yardımcı asistansın ve yalnızca basketbol kuralları hakkında sorulara cevap veriyorsun. "
                        "Yanıtlarını yalnızca verilen bağlam içeriğinden oluştur. "
                        "Eğer sorunun cevabını bilmiyorsan, 'Bu konuda yardımcı olamıyorum.' de. "
                        "Cevaplarını en fazla üç cümle ile ver ve doğru bilgi içerdiğinden emin ol.\n\n"
                        f"Bağlam:\n{context}")
        
        full_prompt = f"{system_prompt}\n\nSoru: {question}"
        
        response = llm.invoke(full_prompt)
        return response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        print(f"AI yanıt hatası: {e}")
        return "Üzgünüm, şu anda yanıt veremiyorum. Lütfen daha sonra tekrar deneyin."

class QueryRequest(BaseModel):
    question: str

@app.on_event("startup")
async def startup_event():
    """Uygulama başlangıcında çalışacak fonksiyon"""
    print("📖 Modeller yükleniyor...")
    initialize_model()
    print("📚 PDF yükleniyor...")
    initialize_vectorstore()

#API'nin Ana Sayfası
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

#Sohbet Oturumlarını Yönetme
@app.get("/sessions")
def list_sessions():
    """Tüm sohbet oturumlarını listele"""
    data = load_chat_history()
    return data.get("sessions", [])

def load_chat_history() -> Dict:
    """Chat geçmişini yükle"""
    if not os.path.exists(SESSIONS_FILE):
        return {"sessions": []}
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Chat geçmişi yükleme hatası: {e}")
        return {"sessions": []}

def save_chat_history(data: Dict) -> None:
    """Chat geçmişini kaydet"""
    try:
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Chat geçmişi kaydetme hatası: {e}")
        raise HTTPException(status_code=500, detail="Chat geçmişi kaydedilemedi")


# AŞAĞIDAN OTURUM YÖNETİMİ İÇİN EK KODLAR
def find_session(data: Dict, session_id: str) -> Optional[Dict]:
    """Belirli bir oturumu bul"""
    return next((s for s in data.get("sessions", []) if s["id"] == session_id), None)

def get_rag_response(question: str) -> str:
    """RAG zincirinden cevap alır ve metin cevabı döndürür."""
    try:
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = rag_chain.invoke({"input": question}) # type: ignore
                return response["answer"]
            except Exception as e:
                if "429" in str(e) or "Resource has been exhausted" in str(e):
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise APIQuotaExceeded("API kotası aşıldı. Lütfen daha sonra tekrar deneyin.") # type: ignore
                    time.sleep(2 ** retry_count)  # Exponential backoff
                else:
                    raise
    except Exception as e:
        print(f"RAG yanıt hatası: {e}")
        if isinstance(e, APIQuotaExceeded): # type: ignore
            return "Üzgünüm, şu anda çok yoğunum. Lütfen biraz sonra tekrar deneyin."
        return "Bir hata oluştu. Lütfen tekrar deneyin."

@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Belirli bir oturumun detaylarını getir"""
    data = load_chat_history()
    session = find_session(data, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")
    return session

#Yeni bir sohbet oturumu oluşturma
@app.post("/sessions")
def create_session(request: QueryRequest):
    """Yeni bir sohbet oturumu oluştur"""
    try:
        data = load_chat_history()
        user_msg = request.question
        bot_msg = get_ai_response(user_msg)

        new_session = {
            "id": str(uuid.uuid4()),
            "title": user_msg[:30] + "..." if len(user_msg) > 30 else user_msg,
            "messages": [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": bot_msg}
            ],
            "created_at": datetime.datetime.now().isoformat()
        }

        data["sessions"].append(new_session)
        save_chat_history(data)
        return new_session
    except Exception as e:
        print(f"Oturum oluşturma hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

#Oturuma yeni mesaj ekleme
@app.post("/sessions/{session_id}/messages")
def add_message(session_id: str, request: QueryRequest):
    """Mevcut oturuma yeni mesaj ekle"""
    try:
        data = load_chat_history()
        session = find_session(data, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Oturum bulunamadı")

        user_msg = request.question
        bot_msg = get_ai_response(user_msg)

        session["messages"].append({"role": "user", "content": user_msg})
        session["messages"].append({"role": "assistant", "content": bot_msg})

        save_chat_history(data)
        return {"question": user_msg, "answer": bot_msg}
    except Exception as e:
        print(f"Mesaj ekleme hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Oturumu sil"""
    try:
        data = load_chat_history()
        data["sessions"] = [s for s in data["sessions"] if s["id"] != session_id]
        save_chat_history(data)
        return {"message": "Oturum silindi"}
    except Exception as e:
        print(f"Oturum silme hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Başlık güncelleme için yeni model ekleyelim
class TitleUpdate(BaseModel):
    title: str

@app.put("/sessions/{session_id}/title")
def update_session_title(session_id: str, request: TitleUpdate):
    """Oturum başlığını günceller."""
    try:
        data = load_chat_history()
        
        # Oturumu bul
        session = None
        for s in data["sessions"]:
            if s["id"] == session_id:
                session = s
                break
                
        if not session:
            raise HTTPException(status_code=404, detail="Oturum bulunamadı")
            
        # Başlığı güncelle
        session["title"] = request.title
        save_chat_history(data)
        
        return {"status": "success", "message": "Başlık güncellendi"}
        
    except Exception as e:
        print(f"Başlık güncelleme hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))