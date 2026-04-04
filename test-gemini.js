const { GoogleGenAI } = require('@google/genai');
require('dotenv').config({path: 'env.txt'});
const ai = new GoogleGenAI({});
ai.models.generateContent({model: 'gemini-2.5-flash', contents: 'Hello!'})
  .then(r => console.log('WORKED:', r.text))
  .catch(e => console.error('FAILED:', e));
