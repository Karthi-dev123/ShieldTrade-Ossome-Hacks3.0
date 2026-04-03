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
    const key = keys[keyIndex];
    keyIndex = (keyIndex + 1) % keys.length;
    
    if (!key) throw new Error("No Gemini API keys found in environment.");

    const ai = new GoogleGenAI({ apiKey: key });
    
    const messages = req.body.messages || [];
    const contents = messages.map(m => {
      // content can be a plain string OR an array of content blocks
      const text = Array.isArray(m.content)
        ? m.content.filter(b => b.type === 'text').map(b => b.text).join(' ')
        : (m.content || '');
      return `${m.role}: ${text}`;
    }).join('\n');
    const model = req.body.model || 'gemini-3-flash-preview';

    console.log(`[Proxy] Using key ${keyIndex} for model ${model}`);

    const response = await ai.models.generateContent({
      model: model,
      contents: contents,
    });

    const text = response.text || '';

    if (req.body.stream) {
      // Return SSE (Server-Sent Events) format for streaming requests
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

      // Send role first, then full text as one chunk, then done
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
