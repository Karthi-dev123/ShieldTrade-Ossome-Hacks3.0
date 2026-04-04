const express = require('express');
const fetch = require('node-fetch'); // Ensure fetch is available, or use global fetch in Node 18+

const app = express();
app.use(express.json({ limit: '50mb' }));

const keys = [
  process.env.GEMINI_API_KEY1,
  process.env.GEMINI_API_KEY2,
  process.env.GEMINI_API_KEY3,
  process.env.GEMINI_API_KEY
].filter(Boolean);

let keyIndex = 0;

app.use((req, res, next) => {
  console.log(`[Proxy] Received ${req.method} ${req.url}`);
  next();
});

app.post('/v1/chat/completions', async (req, res) => {
  try {
    const useOllama = process.env.USE_OLLAMA === 'true';
    if (useOllama) {
      // Ollama logic omitted for brevity, fall back to simple proxy if needed
      const ollamaUrl = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';
      const proxyRes = await fetch(`${ollamaUrl}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req.body)
      });
      if(proxyRes.body){const reader = proxyRes.body.getReader();while(true){const {done, value} = await reader.read();if(done)break;res.write(value);}}res.end();
      return;
    }

    const key = keys[keyIndex];
    if (!key) throw new Error("No Gemini API keys found");
    keyIndex = (keyIndex + 1) % keys.length;

    console.log(`[Proxy] Using Gemini key ${keyIndex} for model ${req.body.model || 'unknown'}`);
    
    // Use the native OpenAI-compatibility layer built into Gemini
    const upstreamUrl = `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`;
    
    const proxyRes = await fetch(upstreamUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${key}`
      },
      body: JSON.stringify(req.body)
    });

    // Pass the exact status code and headers back
    res.status(proxyRes.status);
    Object.entries(proxyRes.headers.raw() || {}).forEach(([k, v]) => {
      res.setHeader(k, v);
    });

    // Pipe the response directly back to the client!
    if(proxyRes.body){const reader = proxyRes.body.getReader();while(true){const {done, value} = await reader.read();if(done)break;res.write(value);}}res.end();
  } catch (err) {
    console.error("[Proxy] Error:", err.message);
    res.status(500).json({ error: { message: err.message } });
  }
});

const PORT = 4000;
app.listen(PORT, () => {
  console.log(`[Proxy] OpenAI-compatible Rotation Proxy running on http://localhost:${PORT}/v1`);
});
