function openChat(initialMessage = '') {
    document.getElementById('home-screen').classList.remove('active');
    document.getElementById('chat-screen').classList.add('active');
    if (initialMessage) { document.getElementById('input').value = initialMessage; send(); }
    else { document.getElementById('input').focus(); }
}
function goHome() {
    document.getElementById('chat-screen').classList.remove('active');
    document.getElementById('home-screen').classList.add('active');
}
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
let pendingIntent = null;
let pendingMFA = false;
input.addEventListener('keypress', (e) => { if (e.key === 'Enter') send(); });
function closeModal(modalId) { document.getElementById(modalId).style.display = 'none'; }
function openInvestModal() { document.getElementById('invest-modal').style.display = 'flex'; }
function submitInvestment() {
    const budget = document.getElementById('inv-budget').value;
    const risk = document.getElementById('inv-risk').value;
    const goal = document.getElementById('inv-goal').value;
    if (!budget || !goal) { alert("Please fill all fields"); return; }
    closeModal('invest-modal');
    quickSend(`invest ${budget} risk ${risk} goal ${goal}`);
}
function addMessage(text, sender, showConfirmButtons = false, data = null) {
    const div = document.createElement('div');
    div.className = `chat-row ${sender}`; 
    const avatar = document.createElement('div');
    avatar.className = sender === 'ai' ? 'ai-avatar' : 'user-avatar'; 
    avatar.textContent = sender === 'ai' ? '🤖' : '👤';
    div.appendChild(avatar);
    const chatText = document.createElement('div');
    chatText.className = 'chat-text';
    if (text) {
        const textNode = document.createElement('div');
        let formattedText = text.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>').replace(/\*(.*?)\*/g, '<i>$1</i>');
        textNode.innerHTML = formattedText; 
        chatText.appendChild(textNode);
    }
    if (data && Array.isArray(data) && data.length > 0 && sender === 'ai') {
        let tableHtml = '';
        if (data[0].card_number !== undefined) {
            tableHtml = `<table style="width:100%; font-size:0.8rem; text-align:left; margin-top:8px; border-collapse: collapse;"><tr style="border-bottom: 1px solid #ddd;"><th style="padding:4px;">Name</th><th style="padding:4px;">Number</th><th style="padding:4px;">Status</th></tr>${data.map(c => `<tr><td style="padding:4px;">${c.card_type}</td><td style="padding:4px;">${c.card_number}</td><td style="padding:4px;">${c.status}</td></tr>`).join('')}</table>`;
        } else if (data[0].amount !== undefined && data[0].note !== undefined) {
            tableHtml = `<table style="width:100%; font-size:0.8rem; text-align:left; margin-top:8px; border-collapse: collapse;"><tr style="border-bottom: 1px solid #ddd;"><th style="padding:4px;">Amount</th><th style="padding:4px;">Note</th></tr>${data.map(tx => `<tr><td style="padding:4px;">฿${tx.amount}</td><td style="padding:4px;">${tx.note}</td></tr>`).join('')}</table>`;
        }
        if (tableHtml) chatText.innerHTML += tableHtml;
    }
    if (showConfirmButtons) {
        const btnDiv = document.createElement('div');
        btnDiv.className = 'confirm-buttons';
        const yesBtn = document.createElement('button');
        yesBtn.className = 'confirm-btn confirm-yes'; yesBtn.textContent = '✅ Yes';
        yesBtn.onclick = () => { btnDiv.remove(); input.value = 'y'; send(); };
        const noBtn = document.createElement('button');
        noBtn.className = 'confirm-btn confirm-no'; noBtn.textContent = '❌ No';
        noBtn.onclick = () => { btnDiv.remove(); input.value = 'n'; send(); };
        btnDiv.appendChild(yesBtn); btnDiv.appendChild(noBtn);
        chatText.appendChild(btnDiv);
    }
    div.appendChild(chatText);
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
}
function showTyping() {
    const div = document.createElement('div');
    div.className = 'chat-row ai'; div.id = 'typing';
    const avatar = document.createElement('div');
    avatar.className = 'ai-avatar'; avatar.textContent = '🤖';
    div.appendChild(avatar);
    const chatText = document.createElement('div');
    chatText.className = 'chat-text'; 
    chatText.innerHTML = '<span class="typing">Thinking</span>';
    div.appendChild(chatText);
    chat.appendChild(div); chat.scrollTop = chat.scrollHeight;
}
function hideTyping() { const el = document.getElementById('typing'); if (el) el.remove(); }
function quickSend(text) { input.value = text; send(); }

async function send() {
    const text = input.value.trim();
    if (!text) return;
    addMessage(text, 'user');
    input.value = '';
    sendBtn.disabled = true;

    if (pendingMFA) {
        try {
            const res = await fetch('/api/verify-otp', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({user_id: 1, otp: text}) });
            const data = await res.json();
            if (!res.ok) addMessage('❌ ' + (data.detail || 'Error'), 'ai');
            else {
                if (data.status === "error") addMessage(data.reply, 'ai');
                else { addMessage(data.reply, 'ai', false, data.data); if (!data.requires_mfa) pendingMFA = false; }
            }
        } catch (e) { addMessage('❌ Error: ' + e.message, 'ai'); pendingMFA = false; }
        sendBtn.disabled = false; input.focus(); return;
    }

    if (pendingIntent && (text.toLowerCase() === 'y' || text.toLowerCase() === 'yes')) {
        try {
            const res = await fetch('/api/confirm', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({intent: pendingIntent, user_id: 1}) });
            const data = await res.json();
            if (!res.ok) addMessage('❌ ' + (data.detail || 'Error'), 'ai');
            else addMessage(data.reply, 'ai', false, data.data);
            pendingIntent = null;
        } catch (e) { addMessage('❌ Error: ' + e.message, 'ai'); }
        sendBtn.disabled = false; return;
    } else if (pendingIntent && (text.toLowerCase() === 'n' || text.toLowerCase() === 'no')) {
        addMessage('❌ Cancelled', 'ai'); pendingIntent = null; sendBtn.disabled = false; return;
    }

    showTyping();
    try {
        const res = await fetch('/api/chat', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message: text, user_id: 1}) });
        const data = await res.json();
        hideTyping();
        if (data.requires_mfa) { pendingMFA = true; pendingIntent = null; addMessage(data.reply, 'ai'); }
        else if (data.requires_confirmation && data.intent) { pendingIntent = data.intent; pendingMFA = false; addMessage(data.reply, 'ai', true); }
        else { pendingIntent = null; pendingMFA = false; addMessage(res.ok ? data.reply : '❌ ' + (data.detail || 'Error'), 'ai', false, data.data); }
    } catch (e) { hideTyping(); addMessage('❌ Error: ' + e.message, 'ai'); }
    sendBtn.disabled = false; input.focus();
}