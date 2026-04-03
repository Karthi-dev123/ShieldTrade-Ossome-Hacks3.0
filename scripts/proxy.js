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
    const contents = messages.map(m => `${m.role}: ${m.content}`).join('\n');
    const model = req.body.model || 'gemini-3-flash-preview';

    console.log(`[Proxy] Using key ${keyIndex} for model ${model}`);

    const response = await ai.models.generateContent({
      model: model,
      contents: contents,
    });

    res.json({
      id: 'proxy-chat',
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: model,
      choices: [{
        index: 0,
        message: {
          role: 'assistant',
          content: response.text
        },
        finish_reason: 'stop'
      }],
      usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }
    });
  } catch (err) {
    console.error("[Proxy] Error:", err.message);
    res.status(500).json({ error: { message: err.message } });
  }
});

const PORT = 4000;
app.listen(PORT, () => {
  console.log(`[Proxy] Local rotation proxy running on http://localhost:${PORT}/v1`);
});
