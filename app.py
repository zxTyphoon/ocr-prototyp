import os
import base64
import json
from io import BytesIO
import gradio as gr
from mistralai import Mistral
from PIL import Image
import time

# Config
VALID_DOCUMENT_EXTENSIONS = {".pdf"}
VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
HISTORY_FILE = "url_history.txt"

def upload_pdf(content, filename, api_key):
    client = Mistral(api_key=api_key)
    uploaded_file = client.files.upload(
        file={"file_name": filename, "content": content},
        purpose="ocr",
    )
    signed_url = client.files.get_signed_url(file_id=uploaded_file.id)
    return signed_url.url

def process_ocr(document_source, api_key):
    client = Mistral(api_key=api_key)
    return client.ocr.process(
        model="mistral-ocr-latest",
        document=document_source,
        include_image_base64=True
    )

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        return []
    except:
        return []

def save_to_history(url):
    if not url or url.strip() == "":
        return load_history()
    
    history = load_history()
    if url in history:
        history.remove(url)  # Remove if exists to add it at the top
    
    history.insert(0, url)  # Add at the beginning
    history = history[:10]  # Keep only 10 most recent
    
    try:
        with open(HISTORY_FILE, "w") as f:
            for item in history:
                f.write(f"{item}\n")
    except:
        pass
    
    return history

def do_ocr(input_type, url, file, progress=gr.Progress()):
    api_key = os.environ.get("MISTRAL")
    
    if not api_key:
        return "Error: MISTRAL API key not found in environment variables.", "Please set your MISTRAL API key as an environment variable named 'MISTRAL'.", [], load_history()
    
    progress(0.1, desc="Starting OCR processing...")
    document_source = None

    if input_type == "URL":
        if not url or url.strip() == "":
            return "Please provide a valid URL.", "", [], load_history()
        
        url_lower = url.lower()
        save_to_history(url)
        
        progress(0.3, desc="URL provided, preparing document...")
        if any(url_lower.endswith(ext) for ext in VALID_IMAGE_EXTENSIONS):
            document_source = {"type": "image_url", "image_url": url.strip()}
        else:
            document_source = {"type": "document_url", "document_url": url.strip()}

    elif input_type == "File upload":
        if not file:
            return "Please upload a file.", "", [], load_history()
        
        progress(0.2, desc="File uploaded, processing...")
        file_name = file.name.lower()
        file_extension = os.path.splitext(file_name)[1]
        
        if file_extension in VALID_DOCUMENT_EXTENSIONS:
            progress(0.3, desc="Processing PDF file...")
            with open(file.name, "rb") as f:
                content = f.read()
            signed_url = upload_pdf(content, os.path.basename(file_name), api_key)
            document_source = {"type": "document_url", "document_url": signed_url}
        elif file_extension in VALID_IMAGE_EXTENSIONS:
            progress(0.4, desc="Processing image file...")
            img = Image.open(file)
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            document_source = {"type": "image_url", "image_url": f"data:image/png;base64,{img_str}"}
        else:
            return f"Error: Unsupported file type. Supported types: {', '.join(VALID_DOCUMENT_EXTENSIONS | VALID_IMAGE_EXTENSIONS)}", "", [], load_history()
    else:
        return "Invalid input type.", "", [], load_history()

    try:
        progress(0.5, desc="Sending to OCR service...")
        ocr_response = process_ocr(document_source, api_key)
        progress(0.7, desc="Processing OCR results...")
    except Exception as e:
        return f"Error processing OCR: {str(e)}", "", [], load_history()

    progress(0.8, desc="Extracting text and images...")
    markdown_text = "\n\n".join(page.markdown for page in ocr_response.pages)
    extracted_text = markdown_text
    rendered_markdown = markdown_text
    images = []

    for page in ocr_response.pages:
        for img in page.images:
            if img.image_base64:
                base64_str = img.image_base64
                if "," in base64_str:
                    base64_str = base64_str.split(",")[1]
                img_bytes = base64.b64decode(base64_str)
                img_pil = Image.open(BytesIO(img_bytes))
                images.append(img_pil)
                img_buffer = BytesIO()
                img_pil.save(img_buffer, format="PNG")
                img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
                data_url = f"data:image/png;base64,{img_base64}"
                rendered_markdown = rendered_markdown.replace(
                    f"![{img.id}]({img.id})", f"![{img.id}]({data_url})"
                )
            else:
                rendered_markdown += f"\n\n[Image Warning: No base64 data for {img.id}]"

    progress(1.0, desc="Complete!")
    history = load_history()
    return extracted_text.strip(), rendered_markdown.strip(), images, history

def update_history_list(history_items):
    if not history_items or len(history_items) == 0:
        return "<p class='no-history'>No history available</p>"
    
    html_list = "<div class='history-list'>"
    for url in history_items:
        html_list += f'<div class="history-item" onclick="(function(){{const urlInputs = document.querySelectorAll(\'input[data-testid=\"textbox\"]\'); for(let i = 0; i < urlInputs.length; i++){{ if(urlInputs[i].labels && urlInputs[i].labels[0] && urlInputs[i].labels[0].textContent.includes(\"Document or Image URL\")){{ urlInputs[i].value = \'{url}\'; urlInputs[i].dispatchEvent(new Event(\'input\', {{ bubbles: true }})); }} }} }})();">{url}</div>'
    html_list += "</div>"
    return html_list

custom_css = """
    body {font-family: 'Helvetica Neue', Helvetica;}
    .container {max-width: 1200px; margin: 0 auto;}
    .gr-button {
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 10px 15px;
        border-radius: 5px;
        transition: all 0.3s ease;
    }
    .gr-button:hover {
        background-color: #45a049;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .gr-button.secondary {
        background-color: #f0f0f0;
        color: #333;
    }
    .gr-button.secondary:hover {
        background-color: #e0e0e0;
    }
    .gr-textbox {margin-bottom: 15px;}
    .tall-radio .gr-radio-item {
        padding: 15px 0;
        min-height: 50px;
        display: flex;
        align-items: center;
    }
    .tall-radio label {font-size: 16px;}
    .file-preview {
        max-height: 200px;
        margin: 10px 0;
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 5px;
    }
    .markdown-container {
        border: 1px solid #eee;
        border-radius: 5px;
        padding: 15px;
        margin-top: 10px;
        background-color: #f9f9f9;
    }
    .history-list {
        max-height: 200px;
        overflow-y: auto;
        border: 1px solid #eee;
        border-radius: 5px;
    }
    .history-item {
        cursor: pointer;
        padding: 8px;
        border-bottom: 1px solid #eee;
    }
    .history-item:hover {
        background-color: #f5f5f5;
    }    
    .no-history {
        padding: 8px;
        color: #999;
        font-style: italic;
    }
    .header-row {
        margin-bottom: 20px;
    }
    .app-header {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-bottom: 20px;
    }
    @media (max-width: 768px) {
        .mobile-full {
            width: 100% !important;
        }
    }
"""

def create_demo():
    with gr.Blocks(
        title="Freudenberg OCR Demo",
        css=custom_css,
        theme=gr.themes.Soft()
    ) as demo:
        url_history_state = gr.State(load_history())
        
        with gr.Row(elem_classes="app-header"):
            gr.Markdown("<h1>Freudenberg OCR Demo</h1>")
        
        with gr.Tabs():
            with gr.TabItem("OCR Tool"):
                with gr.Row():
                    with gr.Column(scale=1, elem_classes="mobile-full"):
                        with gr.Group():
                            input_type = gr.Radio(
                                choices=["URL", "File upload"],
                                label="Input Type",
                                value="URL",
                                elem_classes="tall-radio"
                            )
                            
                            with gr.Group() as url_group:
                                url_input = gr.Textbox(
                                    label="Document or Image URL",
                                    lines=1,
                                    placeholder="Enter URL to a PDF or image (JPG, JPEG, PNG)"
                                )
                            
                            with gr.Group(visible=False) as file_group:
                                file_input = gr.File(
                                    label="Upload PDF or Image",
                                    file_types=[".pdf", ".jpg", ".jpeg", ".png"],
                                    interactive=True
                                )
                                file_preview = gr.Image(label="Preview", visible=False)
                            
                            with gr.Row():
                                submit_btn = gr.Button("Extract Text and Images", variant="primary")
                                clear_btn = gr.Button("Clear", elem_classes="secondary")
                                
                            with gr.Accordion("URL History", open=False):
                                history_display = gr.HTML(update_history_list(load_history()))

                    with gr.Column(scale=2, elem_classes="mobile-full"):
                        with gr.Tabs():
                            with gr.TabItem("Text"):
                                cleaned_output = gr.Textbox(
                                    label="Extracted Plain Text", 
                                    lines=15, 
                                    show_copy_button=True
                                )
                            with gr.TabItem("Markdown"):
                                markdown_container = gr.Markdown(elem_classes="markdown-container")
                            with gr.TabItem("Images"):
                                image_output = gr.Gallery(
                                    label="Extracted Images", 
                                    columns=2, 
                                    height="auto",
                                    show_download_button=True
                                )
            
            with gr.TabItem("Help"):
                gr.Markdown("""
                ## OCR Document Processing Tool
                
                This application uses Mistral AI's OCR capabilities to extract text and images from documents.
                
                ### Features:
                - Extract text from PDF documents and images
                - Preserve document formatting using Markdown
                - Extract and display embedded images
                - URL history for quick access to previously used documents
                
                ### Supported Files:
                - PDF documents (.pdf)
                - Images (.jpg, .jpeg, .png)
                
                ### How to use:
                1. Choose between URL or File upload
                2. Provide a document URL or upload a file
                3. Click "Extract Text and Images"
                4. View the results in the Text, Markdown, or Images tabs
                
                ### Requirements:
                - A valid Mistral API key set as environment variable 'MISTRAL'
                
                ### Tips:
                - For best results with PDFs, ensure they contain text layers or high-quality scanned text
                - Images should be clear and have good contrast for optimal OCR results
                """)
        
        # Define functions for interactions
        def update_input_visibility(choice):
            return gr.update(visible=(choice == "URL")), gr.update(visible=(choice == "File upload"))
        
        def update_file_preview(file):
            if file is None:
                return gr.update(visible=False)
            
            file_ext = os.path.splitext(file.name)[1].lower()
            if file_ext in VALID_IMAGE_EXTENSIONS:
                return gr.update(visible=True, value=file.name)
            return gr.update(visible=False)
        
        def clear_all():
            return (
                gr.update(value=""),  # url_input
                None,                # file_input
                gr.update(value=""), # cleaned_output
                "", # markdown_container
                [], # image_output
                gr.update(visible=False), # file_preview
                update_history_list(load_history()) # history_display
            )
        
        def format_markdown_output(md_text):
            if not md_text:
                return ""
            # Return the raw markdown text directly - the Markdown component will render it
            return md_text
        
        # Connect event handlers
        input_type.change(
            update_input_visibility, 
            inputs=[input_type], 
            outputs=[url_group, file_group]
        )
        
        file_input.change(
            update_file_preview,
            inputs=[file_input],
            outputs=[file_preview]
        )
        
        clear_btn.click(
            clear_all,
            outputs=[
                url_input, file_input, cleaned_output, 
                markdown_container, image_output, file_preview,
                history_display
            ]
        )
        
        submit_btn.click(
            do_ocr,
            inputs=[input_type, url_input, file_input],
            outputs=[cleaned_output, markdown_container, image_output, url_history_state]
        ).then(
            lambda history: update_history_list(history),
            inputs=[url_history_state],
            outputs=[history_display]
        ).then(
            lambda md_text: format_markdown_output(md_text),
            inputs=[markdown_container],
            outputs=[markdown_container]
        )
        
    return demo

if __name__ == "__main__":
    demo = create_demo()
    demo.launch()
