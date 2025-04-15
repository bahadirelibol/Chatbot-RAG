// Global değişken: aktif oturum ID'si
let currentSessionId = null;

// Sayfa yüklendiğinde mevcut oturumları getir ve Yeni Chat butonunu dinle
window.addEventListener("load", () => {
  fetchSessions();
  document
    .getElementById("new-chat-btn")
    .addEventListener("click", function () {
      currentSessionId = null; // Aktif oturum sıfırlanır
      document.getElementById("chat-box").innerHTML = ""; // Chat alanı temizlenir
      document.getElementById("user-input").value = ""; // Giriş alanı temizlenir
    });
});

// 🚀 Enter tuşu ile mesaj gönderme
function handleKeyPress(event) {
  if (event.key === "Enter") sendMessage();
}

// 📩 Mesaj gönderme fonksiyonu (SESSION entegrasyonlu)
async function sendMessage(userInput = null) {
  let inputField = document.getElementById("user-input");
  let userMessage = userInput || inputField.value;

  if (!userMessage.trim()) return;

  addMessage(userMessage, "user-message");
  
  // Loading göstergesi
  let loadingDiv = document.createElement("div");
  loadingDiv.className = "message bot-message loading";
  loadingDiv.innerText = "Düşünüyorum...";
  document.getElementById("chat-box").appendChild(loadingDiv);

  try {
    let response;
    if (!currentSessionId) {
      response = await fetch("/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: userMessage }),
      });
    } else {
      response = await fetch(`/sessions/${currentSessionId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: userMessage }),
      });
    }

    // Loading göstergesini kaldır
    loadingDiv.remove();

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    let data = await response.json();

    if (!currentSessionId && data.id) {
      currentSessionId = data.id;
    }

    let botAnswer = data.answer || data.messages?.[data.messages.length - 1]?.content;
    if (botAnswer) {
      addBotMessageWithSpeakBtn(botAnswer);
    }

    fetchSessions();
  } catch (error) {
    console.error("Error:", error);
    // Loading göstergesini kaldır
    loadingDiv.remove();
    // Hata mesajını göster
    addMessage("Bir hata oluştu. Lütfen tekrar deneyin.", "bot-message error");
  }

  inputField.value = "";
}

// Kullanıcı mesajlarını ekrana yazdırma
function addMessage(text, className) {
  let chatBox = document.getElementById("chat-box");
  let messageDiv = document.createElement("div");
  messageDiv.className = "message " + className;
  messageDiv.innerText = text;
  chatBox.appendChild(messageDiv);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// Bot mesajını seslendirme butonu ile ekleme
function addBotMessageWithSpeakBtn(text) {
  let chatBox = document.getElementById("chat-box");

  let messageDiv = document.createElement("div");
  messageDiv.className = "message bot-message";
  messageDiv.innerText = text;

  let speakBtn = document.createElement("button");
  speakBtn.className = "speak-btn";
  speakBtn.innerText = "🔊";

  let utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "tr-TR";

  let isSpeaking = false; 
  let isPaused = false; 

  speakBtn.onclick = () => {
    if (!isSpeaking) {
      speechSynthesis.cancel();
      speechSynthesis.speak(utterance);
      isSpeaking = true;
      isPaused = false;
    } else if (!isPaused) {
      speechSynthesis.cancel();
      isPaused = true;
    } else {
      speechSynthesis.cancel();
      speechSynthesis.speak(utterance);
      isPaused = false;
    }
  };

  messageDiv.appendChild(speakBtn);
  chatBox.appendChild(messageDiv);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// --- OTURUM YÖNETİMİ ---

// Mevcut tüm oturumları getir
function fetchSessions() {
  fetch("/sessions")
    .then((response) => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      if (Array.isArray(data)) {
        renderSessionList(data);
      } else {
        console.error("Unexpected data format:", data);
      }
    })
    .catch((error) => {
      console.error("Error fetching sessions:", error);
      // Kullanıcıya görsel feedback
      let container = document.getElementById("chat-history");
      container.innerHTML = "<div class='error-message'>Oturumlar yüklenemedi</div>";
    });
}

// Oturum listesini oluştur
function renderSessionList(sessions) {
  let container = document.getElementById("chat-history");
  container.innerHTML = "";
  
  if (!Array.isArray(sessions) || sessions.length === 0) {
    container.innerHTML = "<div class='empty-history'>Henüz sohbet yok</div>";
    return;
  }

  sessions.forEach((session) => {
    if (session && session.id && session.title) {
      let sessionDiv = document.createElement("div");
      sessionDiv.className = "session-item";
      if (session.id === currentSessionId) {
        sessionDiv.classList.add("active");
      }

      // Başlık container'ı
      let titleContainer = document.createElement("div");
      titleContainer.className = "session-title-container";

      // Başlık
      let titleSpan = document.createElement("span");
      titleSpan.className = "session-title";
      titleSpan.textContent = session.title;
      titleSpan.title = "Başlığı düzenlemek için çift tıklayın";

      // Başlık düzenleme fonksiyonu
      titleSpan.addEventListener("dblclick", function(e) {
        e.stopPropagation(); // Oturum seçimini engelle
        
        const input = document.createElement("input");
        input.type = "text";
        input.value = session.title;
        input.className = "session-title-input";

        // Input alanı oluşturulduğunda otomatik seçili gelsin
        input.addEventListener("focus", function() {
          input.select();
        });

        // Input alanından çıkıldığında güncelleme yap
        input.addEventListener("blur", async function() {
          if (input.value.trim() !== session.title) {
            try {
              const response = await fetch(`/sessions/${session.id}/title`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: input.value.trim() })
              });

              if (!response.ok) {
                throw new Error('Başlık güncellenemedi');
              }

              fetchSessions(); // Listeyi yenile
            } catch (error) {
              console.error("Başlık güncelleme hatası:", error);
              alert("Başlık güncellenirken bir hata oluştu!");
            }
          } else {
            titleContainer.replaceChild(titleSpan, input);
          }
        });

        // Enter tuşuna basıldığında güncelleme yap
        input.addEventListener("keypress", function(e) {
          if (e.key === "Enter") {
            input.blur();
          }
        });

        // Escape tuşuna basıldığında iptal et
        input.addEventListener("keydown", function(e) {
          if (e.key === "Escape") {
            titleContainer.replaceChild(titleSpan, input);
          }
        });

        titleContainer.replaceChild(input, titleSpan);
        input.focus();
      });

      // Kontrol butonları
      let controls = document.createElement("div");
      controls.className = "session-controls";

      // Silme butonu
      let deleteBtn = document.createElement("button");
      deleteBtn.innerHTML = "🗑️";
      deleteBtn.className = "session-control-btn delete-btn";
      deleteBtn.title = "Sohbeti sil";
      deleteBtn.onclick = async (e) => {
        e.stopPropagation();
        if (confirm("Bu sohbeti silmek istediğinizden emin misiniz?")) {
          try {
            const response = await fetch(`/sessions/${session.id}`, {
              method: "DELETE"
            });
            if (response.ok) {
              if (session.id === currentSessionId) {
                currentSessionId = null;
                document.getElementById("chat-box").innerHTML = "";
              }
              fetchSessions();
            }
          } catch (error) {
            console.error("Silme hatası:", error);
            alert("Sohbet silinirken bir hata oluştu!");
          }
        }
      };

      titleContainer.appendChild(titleSpan);
      controls.appendChild(deleteBtn);
      sessionDiv.appendChild(titleContainer);
      sessionDiv.appendChild(controls);

      // Oturum seçme
      sessionDiv.addEventListener("click", () => {
        if (currentSessionId !== session.id) {
          loadSession(session.id);
        }
      });

      container.appendChild(sessionDiv);
    }
  });
}

// Belirli bir oturumu GET /sessions/{session_id} endpoint'iyle getirip, chat kutusuna yükler
function loadSession(sessionId) {
  fetch(`/sessions/${sessionId}`)
    .then((response) => response.json())
    .then((data) => {
      currentSessionId = data.id;
      renderSessionMessages(data.messages);
    })
    .catch((error) => console.error("Error loading session:", error));
}

// Oturum içindeki mesajları chat kutusuna yazar
function renderSessionMessages(messages) {
  let chatBox = document.getElementById("chat-box");
  chatBox.innerHTML = "";
  messages.forEach((msg) => {
    let className = msg.role === "user" ? "user-message" : "bot-message";
    addMessage(msg.content, className);
  });
}

// --- SES TANIMA VE "Akif" TETİKLEME --- 

document.addEventListener("DOMContentLoaded", () => {
  const voiceBtn = document.getElementById("voice-btn");
  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    alert("Tarayıcınız ses tanımayı desteklemiyor!");
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = "tr-TR";
  recognition.continuous = true;
  recognition.interimResults = false;

  let isListeningForQuery = false;

  recognition.onresult = (event) => {
    const transcript =
      event.results[event.results.length - 1][0].transcript.toLowerCase();
    console.log("🎤 Algılanan kelime:", transcript);

    if (transcript.includes("akif") && !isListeningForQuery) {
      console.log(
        "✨ 'Akif' kelimesi algılandı. Şimdi tam dinleme moduna geçiyoruz..."
      );
      isListeningForQuery = true;
      recognition.stop();
      setTimeout(listenForQuery, 500);
    }
  };

  recognition.onerror = (event) => {
    console.error("⚠️ Ses Tanıma Hatası:", event.error);
  };

  recognition.start();

  function listenForQuery() {
    const queryRecognition = new SpeechRecognition();
    queryRecognition.lang = "tr-TR";
    queryRecognition.continuous = false;
    queryRecognition.interimResults = false;

    queryRecognition.start();
    console.log("🎤 Kullanıcının sorusu dinleniyor...");

    queryRecognition.onresult = (event) => {
      const userQuery = event.results[0][0].transcript;
      console.log("📨 Algılanan soru:", userQuery);
      sendMessage(userQuery);
      isListeningForQuery = false;
      setTimeout(() => recognition.start(), 1000);
    };

    queryRecognition.onerror = (event) => {
      console.error("⚠️ Soru Tanıma Hatası:", event.error);
      isListeningForQuery = false;
      setTimeout(() => recognition.start(), 1000);
    };
  }

  voiceBtn.onclick = () => {
    listenForQuery();
  };
});
