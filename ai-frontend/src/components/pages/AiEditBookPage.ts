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
          <div id="editor-file-tree" style="width: 250px; border-right: 1px solid var(--ai-color-border, #ccc); overflow-y: auto; padding: 10px; font-size: 13px;">
            <p>Loading...</p>
          </div>
          <div id="editor-main-pane" style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
            <!-- Tab Bar -->
            <div id="editor-tab-bar" style="display: flex; background: var(--ai-color-surface-alt, #f8f8f8); border-bottom: 1px solid var(--ai-color-border, #ccc); overflow-x: auto;">
            </div>
            
            <div style="flex: 1; display: flex; overflow: hidden;">
              <!-- Code Editor -->
              <div id="editor-code-container" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; position: relative;">
                 <div id="editor-cm-wrapper" style="flex: 1; overflow: hidden; position: relative;">
                   <div style="padding: 20px; color: #888;">Select a file from the tree to edit.</div>
                 </div>
              </div>
              
              <!-- Live Preview -->
              <div id="editor-preview-container" style="width: 50%; border-left: 1px solid var(--ai-color-border, #ccc); display: flex; flex-direction: column; background: #fff;">
                 <div style="padding: 4px 8px; background: var(--ai-color-surface-alt, #eee); border-bottom: 1px solid var(--ai-color-border, #ccc); font-size: 11px; color: #666; font-weight: bold;">
                   Live Preview
                 </div>
                 <iframe id="editor-preview-frame" style="flex: 1; border: none; width: 100%; background: #fff;" sandbox="allow-same-origin allow-scripts"></iframe>
              </div>
            </div>
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

  private openFiles: string[] = [];

  private async loadFileTree() {
    if (!this.sessionId) return;
    const res = await fetch(`/ai/editor/api/sessions/${this.sessionId}/files`);
    if (!res.ok) throw new Error("Failed to load files");
    const data = await res.json();
    
    if (!this.fileTree) return;
    this.fileTree.innerHTML = "";

    const files: string[] = data.files.map((f: any) => f.name);
    
    const textFiles = files.filter(f => f.endsWith('.xhtml') || f.endsWith('.html') || f.endsWith('.htm') || f.endsWith('.xml'));
    const styleFiles = files.filter(f => f.endsWith('.css'));
    const imageFiles = files.filter(f => f.endsWith('.png') || f.endsWith('.jpg') || f.endsWith('.jpeg') || f.endsWith('.svg') || f.endsWith('.gif'));
    const fontFiles = files.filter(f => f.endsWith('.ttf') || f.endsWith('.otf') || f.endsWith('.woff') || f.endsWith('.woff2'));
    const miscFiles = files.filter(f => !textFiles.includes(f) && !styleFiles.includes(f) && !imageFiles.includes(f) && !fontFiles.includes(f));

    this.renderTreeCategory("Text", textFiles, "glyphicon-text-background");
    this.renderTreeCategory("Styles", styleFiles, "glyphicon-pencil");
    this.renderTreeCategory("Images", imageFiles, "glyphicon-picture");
    this.renderTreeCategory("Fonts", fontFiles, "glyphicon-font");
    this.renderTreeCategory("Misc", miscFiles, "glyphicon-file");
  }

  private renderTreeCategory(title: string, files: string[], icon: string) {
    if (!this.fileTree || files.length === 0) return;
    
    const details = document.createElement("details");
    details.open = true;
    details.style.marginBottom = "8px";
    
    const summary = document.createElement("summary");
    summary.style.cursor = "pointer";
    summary.style.fontWeight = "bold";
    summary.style.outline = "none";
    summary.innerHTML = `<span class="glyphicon ${icon}" style="font-size: 11px; margin-right: 4px;"></span> ${title} <span class="badge" style="font-size:10px;">${files.length}</span>`;
    details.appendChild(summary);
    
    const ul = document.createElement("ul");
    ul.style.listStyle = "none";
    ul.style.padding = "4px 0 0 16px";
    ul.style.margin = "0";
    
    files.forEach(f => {
      const li = document.createElement("li");
      li.style.cursor = "pointer";
      li.style.padding = "2px 0";
      li.style.wordBreak = "break-all";
      li.style.display = "flex";
      li.style.justifyContent = "space-between";
      li.style.alignItems = "center";
      
      const isImg = f.match(/\.(png|jpg|jpeg|gif|svg)$/i);
      const isFont = f.match(/\.(ttf|otf|woff|woff2)$/i);
      
      const nameSpan = document.createElement("span");
      nameSpan.innerHTML = `<span class="glyphicon ${isImg ? 'glyphicon-picture' : isFont ? 'glyphicon-font' : 'glyphicon-file'}" style="font-size: 10px; color: #888; margin-right: 4px;"></span>${f}`;
      nameSpan.style.flex = "1";
      nameSpan.addEventListener("click", () => this.openFile(f));
      
      const actionsSpan = document.createElement("span");
      actionsSpan.style.display = "none";
      actionsSpan.style.gap = "4px";
      
      const renameBtn = document.createElement("span");
      renameBtn.className = "glyphicon glyphicon-edit";
      renameBtn.title = "Rename";
      renameBtn.style.color = "#888";
      renameBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.renameFile(f);
      });
      
      const delBtn = document.createElement("span");
      delBtn.className = "glyphicon glyphicon-trash";
      delBtn.title = "Delete";
      delBtn.style.color = "#d9534f";
      delBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.deleteFile(f);
      });
      
      actionsSpan.appendChild(renameBtn);
      actionsSpan.appendChild(delBtn);
      
      li.appendChild(nameSpan);
      li.appendChild(actionsSpan);
      
      li.addEventListener("mouseover", () => {
        nameSpan.style.textDecoration = "underline";
        actionsSpan.style.display = "flex";
      });
      li.addEventListener("mouseout", () => {
        nameSpan.style.textDecoration = "none";
        actionsSpan.style.display = "none";
      });
      ul.appendChild(li);
    });
    
    details.appendChild(ul);
    this.fileTree.appendChild(details);
  }

  private renderTabs() {
    const tabBar = this.container.querySelector("#editor-tab-bar");
    if (!tabBar) return;
    tabBar.innerHTML = "";
    
    this.openFiles.forEach(f => {
      const tab = document.createElement("div");
      const isActive = (f === this.currentFile);
      tab.style.padding = "6px 12px";
      tab.style.cursor = "pointer";
      tab.style.borderRight = "1px solid var(--ai-color-border, #ccc)";
      tab.style.background = isActive ? "var(--ai-color-surface, #fff)" : "var(--ai-color-surface-alt, #f8f8f8)";
      tab.style.borderBottom = isActive ? "2px solid var(--ai-color-primary, #337ab7)" : "none";
      tab.style.fontWeight = isActive ? "bold" : "normal";
      tab.style.display = "flex";
      tab.style.alignItems = "center";
      tab.style.gap = "8px";
      tab.style.fontSize = "12px";
      
      const nameSpan = document.createElement("span");
      const parts = f.split('/');
      nameSpan.textContent = parts[parts.length - 1] ?? "";
      tab.appendChild(nameSpan);
      
      const closeBtn = document.createElement("span");
      closeBtn.className = "glyphicon glyphicon-remove";
      closeBtn.style.fontSize = "10px";
      closeBtn.style.color = "#999";
      closeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.closeFile(f);
      });
      tab.appendChild(closeBtn);
      
      tab.addEventListener("click", () => this.openFile(f));
      tabBar.appendChild(tab);
    });
  }

  private closeFile(filename: string) {
    this.openFiles = this.openFiles.filter(f => f !== filename);
    if (this.currentFile === filename) {
      this.currentFile = this.openFiles.length > 0 ? (this.openFiles[this.openFiles.length - 1] ?? null) : null;
      if (this.currentFile) {
        this.openFile(this.currentFile);
      } else {
        if (this.editorContainer) this.editorContainer.innerHTML = '<div style="padding: 20px; color: #888;">Select a file from the tree to edit.</div>';
        this.editor = null;
        if (this.saveBtn) this.saveBtn.disabled = true;
        this.renderTabs();
        this.updatePreview();
      }
    } else {
      this.renderTabs();
    }
  }

  private async renameFile(filename: string) {
    if (!this.sessionId) return;
    const parts = filename.split('/');
    const basename = parts.pop();
    const newName = prompt(`Rename ${basename} to:`, basename);
    
    if (!newName || newName === basename) return;
    
    parts.push(newName);
    const fullNewName = parts.join('/');
    
    try {
      const csrfMeta = document.querySelector('meta[name="csrf-token"]') as HTMLMetaElement;
      const res = await fetch(`/ai/editor/api/sessions/${this.sessionId}/rename`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfMeta ? csrfMeta.content : ''
        },
        body: JSON.stringify({ old_name: filename, new_name: fullNewName })
      });
      
      if (!res.ok) throw new Error("Rename failed");
      
      if (this.openFiles.includes(filename)) {
         this.openFiles = this.openFiles.map(f => f === filename ? fullNewName : f);
         if (this.currentFile === filename) this.currentFile = fullNewName;
      }
      
      this.renderTabs();
      await this.loadFileTree();
    } catch (e: any) {
      alert(e.message);
    }
  }

  private async deleteFile(filename: string) {
    if (!this.sessionId) return;
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;
    
    try {
      const csrfMeta = document.querySelector('meta[name="csrf-token"]') as HTMLMetaElement;
      const res = await fetch(`/ai/editor/api/sessions/${this.sessionId}/file?name=${encodeURIComponent(filename)}`, {
        method: "DELETE",
        headers: {
          "X-CSRFToken": csrfMeta ? csrfMeta.content : ''
        }
      });
      
      if (!res.ok) throw new Error("Delete failed");
      
      this.closeFile(filename);
      await this.loadFileTree();
    } catch (e: any) {
      alert(e.message);
    }
  }

  private async openFile(filename: string) {
    if (!this.sessionId || !this.editorContainer) return;
    
    if (!this.openFiles.includes(filename)) {
      this.openFiles.push(filename);
    }
    this.currentFile = filename;
    this.renderTabs();
    
    // Check if binary (images/fonts)
    const isImage = filename.match(/\.(png|jpg|jpeg|gif|svg)$/i);
    const isFont = filename.match(/\.(ttf|otf|woff|woff2)$/i);
    
    if (isFont) {
       this.editorContainer.innerHTML = '<div style="padding: 20px; color: #888;">Cannot edit font files. Preview not available.</div>';
       this.editor = null;
       if (this.saveBtn) this.saveBtn.disabled = true;
       return;
    }
    
    if (isImage) {
       this.editorContainer.innerHTML = `<div style="padding: 20px; text-align: center;"><img src="/ai/editor/api/sessions/${this.sessionId}/preview/${encodeURIComponent(filename)}" style="max-width: 100%; max-height: 60vh; border: 1px solid #ccc;" /></div>`;
       this.editor = null;
       if (this.saveBtn) this.saveBtn.disabled = true;
       return;
    }
    
    // It is a text file
    const res = await fetch(`/ai/editor/api/sessions/${this.sessionId}/file?name=${encodeURIComponent(filename)}`);
    if (!res.ok) {
      alert("Failed to load file");
      return;
    }
    
    const text = await res.text();
    
    if (!this.editor) {
      this.editorContainer.innerHTML = "";
      this.editor = new AiCodeEditor(this.editorContainer, text, filename, (content) => {
        this.dirty = true;
        if (this.saveBtn) this.saveBtn.disabled = false;
      });
    } else {
      this.editor.setContent(text, filename);
    }
    
    this.dirty = false;
    if (this.saveBtn) this.saveBtn.disabled = true;
    
    this.updatePreview();
  }

  private updatePreview() {
    const frame = this.container.querySelector("#editor-preview-frame") as HTMLIFrameElement;
    if (!frame || !this.sessionId || !this.currentFile) return;
    
    const isHtml = this.currentFile.match(/\.(xhtml|html|htm)$/i);
    if (isHtml) {
      frame.src = `/ai/editor/api/sessions/${this.sessionId}/preview/${encodeURIComponent(this.currentFile)}`;
    } else {
      // If we are editing CSS or OPF, we could technically keep the old preview loaded and inject new CSS, 
      // but for E1 MVP, we just don't touch the preview src if it's not HTML.
    }
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
      this.updatePreview();
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
