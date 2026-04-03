const express = require('express');
const { GoogleGenAI } = require('@google/genai');

const app = express();
app.use(express.json({ limit: '50mb' }));

const keys = [
  process.env.GEMINI_API_KEY1,
  process.env.GEMINI_API_KEY2,
  process.env.GEMINI_API_KEY3
].filter(Boolean);

let keyIndex = 0;

app.use((req, res, next) => {
  console.log(`[Proxy] Received ${req.method} ${req.url}`);
  next();
});

app.use(async (req, res) => {
  try {
    const useOllama = process.env.USE_OLLAMA === 'true';
    const model = req.body.model || 'gemini-3-flash-preview';
    const messages = req.body.messages || [];
    
    // Normalize content for both APIs
    const contents = messages.map(m => {
      const text = Array.isArray(m.content)
        ? m.content.filter(b => b.type === 'text').map(b => b.text).join(' ')
        : (m.content || '');
      return `${m.role}: ${text}`;
    }).join('\n');

    if (useOllama) {
      const ollamaUrl = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';
      const ollamaKey = process.env.OLLAMA_API_KEY || '';
      console.log(`[Proxy] Using Ollama at ${ollamaUrl}`);
      
      const payload = {
        model: model,
        messages: [{ role: 'user', content: contents }],
        stream: !!req.body.stream
      };

      const response = await fetch(`${ollamaUrl}/v1/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(ollamaKey && { 'Authorization': `Bearer ${ollamaKey}` })
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error(`Ollama Error: ${response.statusText}`);
      }

      if (req.body.stream) {
        res.setHeader('Content-Type', 'text/event-stream');
        res.setHeader('Cache-Control', 'no-cache');
        res.setHeader('Connection', 'keep-alive');
        
        const reader = response.body.getReader();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          res.write(value);
        }
        res.end();
      } else {
        const data = await response.json();
        res.json(data);
      }
      return;
    }

    // Default to Gemini Rotation
    const key = keys[keyIndex];
    keyIndex = (keyIndex + 1) % keys.length;
    
    if (!key) throw new Error("No Gemini API keys found in environment.");

    const ai = new GoogleGenAI({ apiKey: key });
    console.log(`[Proxy] Using key ${keyIndex} for model ${model}`);

    const response = await ai.models.generateContent({
      model: model,
      contents: contents,
    });

    const text = response.text || '';

    if (req.body.stream) {
      res.setHeader('Content-Type', 'text/event-stream');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');

      const chunk = (delta) => JSON.stringify({
        id: 'proxy-chat',
        object: 'chat.completion.chunk',
        created: Math.floor(Date.now() / 1000),
        model: model,
        choices: [{ index: 0, delta, finish_reason: null }],
      });

      res.write(`data: ${chunk({ role: 'assistant', content: '' })}\n\n`);
      res.write(`data: ${chunk({ content: text })}\n\n`);
      res.write(`data: ${JSON.stringify({
        id: 'proxy-chat', object: 'chat.completion.chunk',
        created: Math.floor(Date.now() / 1000), model: model,
        choices: [{ index: 0, delta: {}, finish_reason: 'stop' }],
      })}\n\n`);
      res.write('data: [DONE]\n\n');
      res.end();
    } else {
      res.json({
        id: 'proxy-chat',
        object: 'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model: model,
        choices: [{
          index: 0,
          message: { role: 'assistant', content: text },
          finish_reason: 'stop'
        }],
        usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }
      });
    }
  } catch (err) {
    console.error("[Proxy] Error:", err.message);
    res.status(500).json({ error: { message: err.message } });
  }
});

const PORT = 4000;
app.listen(PORT, () => {
  console.log(`[Proxy] Local rotation proxy running on http://localhost:${PORT}/v1`);
});
