# Freudenberg OCR Demo

A web application that leverages Mistral AI's OCR capabilities to extract text and images from documents.

## Features

- Extract text from PDF documents and images
- Preserve document formatting using Markdown
- Extract and display embedded images
- URL history for quick access to previously used documents
- Modern UI with dark/light mode toggle
- Mobile-responsive design

## Installation

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set your Mistral API key as an environment variable

## Usage

1. Run the application:
   ```
   python app.py
   ```

2. Open your web browser at the URL displayed in the console (typically http://127.0.0.1:7860)

3. Use the application by either:
   - Providing a URL to a PDF document or image
   - Uploading a PDF document or image file

4. Click "Extract Text and Images" and view the results

## Supported File Types

- PDF documents (.pdf)
- Images (.jpg, .jpeg, .png)

## Requirements

- Python 3.8+
- Mistral AI API key
