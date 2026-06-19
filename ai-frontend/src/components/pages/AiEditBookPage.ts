import type { IAiApiClient } from "../../types/api";
import { AiCodeEditor } from "../organisms/AiCodeEditor";

export class AiEditBookPage {
  private sessionId: string | null = null;
  private fileTree: HTMLElement | null = null;
  private editorContainer: HTMLElement | null = null;
  private editor: AiCodeEditor | null = null;
  private currentFile: string | null = null;
  private saveBtn: HTMLButtonElement | null = null;
  private commitBtn: HTMLButtonElement | null = null;
  private dirty = false;

  constructor(
    private readonly container: HTMLElement,
    private readonly client: IAiApiClient,
    private readonly bookId: number,
    private readonly format: string
  ) {}

  public async mount() {
    this.container.innerHTML = `
      <div class="panel panel-default">
        <div class="panel-heading" style="display:flex; justify-content:space-between; align-items:center;">
          <h3 class="panel-title">Edit Book: ${this.bookId} (${this.format})</h3>
          <div>
            <button id="editor-save-btn" class="btn btn-primary btn-sm" disabled>Save File</button>
            <button id="editor-commit-btn" class="btn btn-success btn-sm" disabled>Commit to Library</button>
          </div>
        </div>
        <div class="panel-body" style="display:flex; height: 75vh; padding: 0;">
          <div id="editor-file-tree" style="width: 250px; border-right: 1px solid var(--ai-color-border, #ccc); overflow-y: auto; padding: 10px;">
            <p>Loading...</p>
          </div>
          <div id="editor-code-container" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column;">
             <div style="padding: 10px; border-bottom: 1px solid var(--ai-color-border, #ccc); color: var(--ai-color-text-muted);">
               <span id="editor-current-file">Select a file from the left to edit</span>
             </div>
             <div id="editor-cm-wrapper" style="flex: 1; overflow: hidden; position: relative;"></div>
          </div>
        </div>
      </div>
    `;

    this.fileTree = this.container.querySelector("#editor-file-tree");
    this.editorContainer = this.container.querySelector("#editor-cm-wrapper");
    this.saveBtn = this.container.querySelector("#editor-save-btn");
    this.commitBtn = this.container.querySelector("#editor-commit-btn");

    this.saveBtn?.addEventListener("click", () => this.saveCurrentFile());
    this.commitBtn?.addEventListener("click", () => this.commitSession());

    try {
      await this.initSession();
    } catch (e: any) {
      if (this.fileTree) {
        this.fileTree.innerHTML = `<p class="text-danger">Error: ${e.message}</p>`;
      }
    }
  }

  private async initSession() {
    const csrfMeta = document.querySelector('meta[name="csrf-token"]') as HTMLMetaElement;
    const csrfToken = csrfMeta ? csrfMeta.content : '';

    const res = await fetch("/ai/editor/api/sessions", {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken 
      },
      body: JSON.stringify({ book_id: this.bookId, format: this.format })
    });
    
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error || "Failed to init session");
    }

    const data = await res.json();
    this.sessionId = data.id;

    await this.loadFileTree();
    
    if (this.commitBtn) {
      this.commitBtn.disabled = false;
    }
  }

  private async loadFileTree() {
    if (!this.sessionId) return;
    const res = await fetch(`/ai/editor/api/sessions/${this.sessionId}/files`);
    if (!res.ok) throw new Error("Failed to load files");
    const data = await res.json();
    
    if (this.fileTree) {
      this.fileTree.innerHTML = "";
      const ul = document.createElement("ul");
      ul.style.listStyle = "none";
      ul.style.padding = "0";
      
      data.files.forEach((f: any) => {
        const li = document.createElement("li");
        li.style.cursor = "pointer";
        li.style.padding = "4px 0";
        li.style.wordBreak = "break-all";
        li.textContent = f.name;
        li.addEventListener("click", () => this.openFile(f.name));
        li.addEventListener("mouseover", () => li.style.textDecoration = "underline");
        li.addEventListener("mouseout", () => li.style.textDecoration = "none");
        ul.appendChild(li);
      });
      
      this.fileTree.appendChild(ul);
    }
  }

  private async openFile(filename: string) {
    if (!this.sessionId || !this.editorContainer) return;
    
    const res = await fetch(`/ai/editor/api/sessions/${this.sessionId}/file?name=${encodeURIComponent(filename)}`);
    if (!res.ok) {
      alert("Failed to load file");
      return;
    }
    
    const text = await res.text();
    this.currentFile = filename;
    
    const titleEl = this.container.querySelector("#editor-current-file");
    if (titleEl) titleEl.textContent = filename;
    
    if (!this.editor) {
      this.editor = new AiCodeEditor(this.editorContainer, text, filename, (content) => {
        this.dirty = true;
        if (this.saveBtn) this.saveBtn.disabled = false;
      });
    } else {
      this.editor.setContent(text, filename);
    }
    
    this.dirty = false;
    if (this.saveBtn) this.saveBtn.disabled = true;
  }

  private async saveCurrentFile() {
    if (!this.sessionId || !this.currentFile || !this.editor) return;
    
    const content = this.editor.getContent();
    
    if (this.saveBtn) {
      this.saveBtn.disabled = true;
      this.saveBtn.textContent = "Saving...";
    }
    
    try {
      const csrfMeta = document.querySelector('meta[name="csrf-token"]') as HTMLMetaElement;
      const csrfToken = csrfMeta ? csrfMeta.content : '';

      const res = await fetch(`/ai/editor/api/sessions/${this.sessionId}/file?name=${encodeURIComponent(this.currentFile)}`, {
        method: "PUT",
        headers: {
          "X-CSRFToken": csrfToken 
        },
        body: content
      });
      
      if (!res.ok) throw new Error("Save failed");
      
      this.dirty = false;
    } catch (e: any) {
      alert("Error saving: " + e.message);
      if (this.saveBtn) this.saveBtn.disabled = false;
    } finally {
      if (this.saveBtn) this.saveBtn.textContent = "Save File";
    }
  }

  private async commitSession() {
    if (!this.sessionId) return;
    
    if (!confirm("This will overwrite the book in Calibre. Continue?")) return;
    
    if (this.commitBtn) {
      this.commitBtn.disabled = true;
      this.commitBtn.textContent = "Committing...";
    }
    
    try {
      const csrfMeta = document.querySelector('meta[name="csrf-token"]') as HTMLMetaElement;
      const csrfToken = csrfMeta ? csrfMeta.content : '';

      const res = await fetch(`/ai/editor/api/sessions/${this.sessionId}/commit`, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken 
        }
      });
      
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.error || "Commit failed");
      }
      
      alert("Successfully committed to Calibre!");
    } catch (e: any) {
      alert("Error committing: " + e.message);
      if (this.commitBtn) {
        this.commitBtn.disabled = false;
        this.commitBtn.textContent = "Commit to Library";
      }
    }
  }
}
