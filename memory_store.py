"""
memory_store.py
Knowledge base (FAISS + sentence-transformer embeddings) and advice
generator (GPT-2). Both are heavy ML dependencies, so they are only
loaded when ENABLE_AI_ADVICE=true is set in the environment. By
default the app runs on a fast, dependency-light rule-based fallback
so it deploys cleanly on small/free hosting tiers. Set ENABLE_AI_ADVICE
if you're deploying somewhere with more RAM/CPU and want the full
FAISS + GPT-2 pipeline from the original project.
"""

import os

AI_ADVICE_ENABLED = os.environ.get("ENABLE_AI_ADVICE", "false").lower() == "true"


class FertilizerMemory:
    def __init__(self):
        self.default_text = "Balanced NPK fertilizer is recommended for general crop growth."
        self.vectorstore = None
        self.embeddings = None
        self.generator = None

        self.knowledge_texts = [
            "Rice usually responds well to NPK fertilizer for steady vegetative growth and grain development.",
            "Wheat generally benefits from a balanced NPK fertilizer for uniform crop growth.",
            "Maize often needs nitrogen support, so Urea with DAP is a common recommendation.",
            "Vegetables usually grow better with compost combined with NPK fertilizer to improve soil health.",
            "If soil nitrogen is low, Urea is commonly recommended as a nitrogen-rich fertilizer.",
            "If soil phosphorus is low, DAP is commonly recommended to improve phosphorus availability.",
            "If soil potassium is low, MOP or Potash is commonly recommended.",
            "If soil pH is below 6, applying lime may help raise the soil pH.",
            "If soil pH is above 7.5, gypsum or organic compost may help improve soil condition.",
            "Sugarcane is a heavy feeder and benefits from split doses of nitrogen through the growing season.",
            "Groundnut benefits from gypsum applied at flowering to support healthy pod development.",
            "Organic farms typically substitute Urea, DAP and MOP with vermicompost, bone meal and wood ash.",
            "In the kharif (monsoon) season, split nitrogen doses reduce nutrient loss from heavy rainfall.",
            "In the rabi (winter) season, irrigation timing matters as much as fertilizer timing since rainfall is scarce.",
            "High humidity combined with excess nitrogen can increase fungal disease pressure on leafy crops.",
        ]

        if AI_ADVICE_ENABLED:
            self._load_knowledge_base()
            self._load_gpt2()

    def _load_knowledge_base(self):
        """Create a small FAISS knowledge base using Hugging Face embeddings."""
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            from langchain_community.vectorstores import FAISS
            from langchain_core.documents import Document

            knowledge_docs = [Document(page_content=t) for t in self.knowledge_texts]
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            self.vectorstore = FAISS.from_documents(knowledge_docs, self.embeddings)
        except Exception:
            self.vectorstore = None

    def _load_gpt2(self):
        """Load GPT-2 text generator."""
        try:
            from transformers import pipeline

            self.generator = pipeline(
                "text-generation",
                model="gpt2",
                tokenizer="gpt2",
                max_new_tokens=80,
                truncation=True,
                pad_token_id=50256,
            )
        except Exception:
            self.generator = None

    def default_recommendation(self):
        return self.default_text

    def _keyword_retrieve(self, query, k=2):
        """Lightweight fallback retrieval used when FAISS isn't loaded."""
        query_words = set(query.lower().replace(",", " ").split())
        scored = []
        for text in self.knowledge_texts:
            text_words = set(text.lower().replace(",", " ").split())
            score = len(query_words & text_words)
            scored.append((score, text))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [t for score, t in scored[:k] if score > 0]
        return top if top else [self.default_text]

    def retrieve_context(self, query, k=2):
        if self.vectorstore is None:
            return self._keyword_retrieve(query, k=k)
        results = self.vectorstore.similarity_search(query, k=k)
        return [doc.page_content for doc in results]

    def generate_advice(self, crop, nitrogen, phosphorus, potassium, ph, fertilizers, context):
        """Generate a short explanation with GPT-2, or a clear rule-based fallback."""
        if self.generator is None:
            note = context[0] if context else ""
            return (
                f"For {crop}, with nitrogen {nitrogen}, phosphorus {phosphorus}, "
                f"potassium {potassium} and soil pH {ph}, the recommended input is "
                f"{fertilizers}. {note}"
            ).strip()

        prompt = (
            "Give a short fertilizer recommendation in simple English.\n"
            f"Crop: {crop}\n"
            f"Nitrogen: {nitrogen}\n"
            f"Phosphorus: {phosphorus}\n"
            f"Potassium: {potassium}\n"
            f"Soil pH: {ph}\n"
            f"Recommended fertilizers: {fertilizers}\n"
            f"Reference notes: {' '.join(context)}\n"
            "Advice:"
        )
        try:
            result = self.generator(prompt, num_return_sequences=1)[0]["generated_text"]
            advice = result.split("Advice:", 1)[-1].strip()
            return advice if advice else self.default_recommendation()
        except Exception:
            return (
                f"Recommended fertilizer for {crop} is {fertilizers}. "
                f"This is based on nutrient levels and soil pH of {ph}."
            )
