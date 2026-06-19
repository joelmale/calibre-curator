import { EditorView, basicSetup } from "codemirror";
import { EditorState } from "@codemirror/state";
import { html } from "@codemirror/lang-html";
import { css } from "@codemirror/lang-css";
import { xml } from "@codemirror/lang-xml";
import { javascript } from "@codemirror/lang-javascript";

export class AiCodeEditor {
  private view: EditorView;
  private onChange: (content: string) => void;

  constructor(
    container: HTMLElement,
    initialContent: string,
    filename: string,
    onChange: (content: string) => void
  ) {
    this.onChange = onChange;

    const state = this.createState(initialContent, filename);
    this.view = new EditorView({
      state,
      parent: container,
    });
  }

  private createState(content: string, filename: string): EditorState {
    let langExt: any[] = [];
    const lowerName = filename.toLowerCase();
    if (lowerName.endsWith(".html") || lowerName.endsWith(".xhtml") || lowerName.endsWith(".htm")) {
      langExt = [html()];
    } else if (lowerName.endsWith(".css")) {
      langExt = [css()];
    } else if (lowerName.endsWith(".xml") || lowerName.endsWith(".opf") || lowerName.endsWith(".ncx")) {
      langExt = [xml()];
    } else if (lowerName.endsWith(".js")) {
      langExt = [javascript()];
    }

    return EditorState.create({
      doc: content,
      extensions: [
        basicSetup,
        ...langExt,
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            this.onChange(update.state.doc.toString());
          }
        }),
      ],
    });
  }

  public setContent(content: string, filename: string) {
    this.view.setState(this.createState(content, filename));
  }

  public getContent(): string {
    return this.view.state.doc.toString();
  }

  public destroy() {
    this.view.destroy();
  }
}
