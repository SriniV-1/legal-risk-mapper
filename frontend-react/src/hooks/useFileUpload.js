import { useState, useRef } from "react";
import { extractText } from "../api/client.js";

export default function useFileUpload() {
  const [tab, setTab] = useState("text");
  const [inputText, setInputText] = useState("");
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef(null);

  function loadSample(key, samples) {
    setInputText(samples[key].text);
    setTab("text");
  }

  function handleFileSet(f) {
    setFile(f);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files[0]) handleFileSet(e.dataTransfer.files[0]);
  }

  function clearInput() {
    setInputText("");
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  /**
   * Resolves input to plain text. Handles PDF extraction via the API.
   * @param {function} setLoadingMsg - callback to update loading message during PDF extraction
   * @returns {Promise<string>} the resolved text
   */
  async function getResolvedText(setLoadingMsg) {
    if (tab === "file" && file) {
      const name = file.name.toLowerCase();
      if (name.endsWith(".pdf")) {
        setLoadingMsg("Extracting text from PDF…");
        const res = await extractText(file);
        return res.text || "";
      } else {
        return await file.text();
      }
    }
    return inputText.trim();
  }

  return {
    tab,
    setTab,
    inputText,
    setInputText,
    file,
    dragging,
    setDragging,
    fileInputRef,
    loadSample,
    handleFileSet,
    clearInput,
    getResolvedText,
  };
}
