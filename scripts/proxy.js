const express = require('express');

const app = express();
app.use(express.json({ limit: '50mb' }));

app.use((req, res, next) => {
  console.log(`[Proxy] Received ${req.method} ${req.url}`);
  next();
});

app.get('/v1/models', async (req, res) => {
  try {
    const ollamaUrl = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';
    const ollamaKey = process.env.OLLAMA_API_KEY || '';

    const response = await fetch(`${ollamaUrl}/v1/models`, {
      method: 'GET',
      headers: {
        ...(ollamaKey && { 'Authorization': `Bearer ${ollamaKey}` })
      }
    });

    if (!response.ok) {
      const failure = await response.text();
      throw new Error(`Ollama Error (${response.status}): ${failure || response.statusText}`);
    }

    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error('[Proxy] Error:', err.message);
    res.status(500).json({ error: { message: err.message } });
  }
});

app.use(async (req, res) => {
  try {
    const ollamaUrl = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';
    const ollamaKey = process.env.OLLAMA_API_KEY || '';
    const defaultModel = process.env.OLLAMA_MODEL || 'llama3.2:3b';
    const requestedModel = req.body.model;
    const model =
      !requestedModel ||
      requestedModel === 'local-ollama' ||
      requestedModel.startsWith('gemini-')
        ? defaultModel
        : requestedModel;
    const messages = req.body.messages || [];
    
    // Build fallback text if the caller does not send a standard messages array.
    const contents = messages.map(m => {
      const text = Array.isArray(m.content)
        ? m.content.filter(b => b.type === 'text').map(b => b.text).join(' ')
        : (m.content || '');
      return `${m.role}: ${text}`;
    }).join('\n');

    console.log(`[Proxy] Using Ollama at ${ollamaUrl} (model: ${model})`);

    const payload = {
      ...req.body,
      model,
      messages: Array.isArray(messages) && messages.length
        ? messages
        : [{ role: 'user', content: contents || 'Respond to the user prompt.' }],
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
      const failure = await response.text();
      throw new Error(`Ollama Error (${response.status}): ${failure || response.statusText}`);
    }

    if (req.body.stream) {
      res.setHeader('Content-Type', 'text/event-stream');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let sawDone = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        if (chunk.includes('[DONE]')) sawDone = true;
        res.write(value);
      }
      if (!sawDone) {
        res.write('data: [DONE]\n\n');
      }
      res.end();
    } else {
      const data = await response.json();
      res.json(data);
    }
  } catch (err) {
    console.error("[Proxy] Error:", err.message);
    res.status(500).json({ error: { message: err.message } });
  }
});

const PORT = 4000;
app.listen(PORT, () => {
  console.log(`[Proxy] Local Ollama proxy running on http://localhost:${PORT}/v1`);
});
