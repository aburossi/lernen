import streamlit as st
import time
from openai import OpenAI
import json
from PyPDF2 import PdfReader
from fpdf import FPDF

# Set page config
st.set_page_config(page_title="Exam Creator", page_icon="📝")

__version__ = "1.2.0"

# Main app functions
def stream_llm_response(messages, model_params, api_key):
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model_params["model"] if "model" in model_params else "gpt-4o-mini",
        messages=messages,
        temperature=model_params["temperature"] if "temperature" in model_params else 0.5,
        max_tokens=10096,
    )
    return response.choices[0].message.content

def extract_text_from_pdf(pdf_file):
    pdf_reader = PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def chunk_text(text, max_tokens=3000):
    sentences = text.split('. ')
    chunks = []
    chunk = ""
    for sentence in sentences:
        if len(chunk) + len(sentence) > max_tokens:
            chunks.append(chunk)
            chunk = sentence + ". "
        else:
            chunk += sentence + ". "
    if chunk:
        chunks.append(chunk)
    return chunks

def generate_mc_questions(content_text, api_key):
    system_prompt = (
        "Sie sind ein Lehrer für Allgemeinbildung und sollen eine Prüfung zum Thema des eingereichten PDFs erstellen. "
        "Verwenden Sie den Inhalt des PDFs (bitte gründlich analysieren) und erstellen Sie eine Multiple-Choice-Prüfung auf Oberstufenniveau. "
        "Die Prüfung soll sowohl Fragen mit einer richtigen Antwort als auch Fragen mit mehreren richtigen Antworten enthalten. "
        "Kennzeichnen Sie die Fragen entsprechend, damit die Schüler wissen, wie viele Optionen sie auswählen sollen. "
        "Erstellen Sie so viele Prüfungsfragen, wie nötig sind, um den gesamten Inhalt abzudecken, aber maximal 20 Fragen. "
        "Geben Sie die Ausgabe im JSON-Format an. "
        "Das JSON sollte folgende Struktur haben: [{'question': '...', 'choices': ['...'], 'correct_answer': '...', 'explanation': '...'}, ...]. "
        "Stellen Sie sicher, dass das JSON gültig und korrekt formatiert ist."
    )
    user_prompt = (
        "Using the following content from the uploaded PDF, create multiple-choice and single-choice questions. "
        "Ensure that each question is based on the information provided in the PDF content. "
        "Mark questions appropriately so that students know how many options to select. "
        "Create as many questions as necessary to cover the entire content, but no more than 20 questions. "
        "Provide the output in JSON format with the following structure: "
        "[{'question': '...', 'choices': ['...'], 'correct_answer': '...', 'explanation': '...'}, ...]. "
        "Ensure the JSON is valid and properly formatted.\n\nPDF Content:\n\n"
    ) + content_text

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        response = stream_llm_response(messages, model_params={"model": "gpt-4o-mini", "temperature": 0.5}, api_key=api_key)
        return response, None
    except Exception as e:
        return None, str(e)

def parse_generated_questions(response):
    try:
        json_start = response.find('[')
        json_end = response.rfind(']') + 1
        if json_start == -1 or json_end == 0:
            return None, f"No JSON data found in the response. First 500 characters of response:\n{response[:500]}..."
        json_str = response[json_start:json_end]

        questions = json.loads(json_str)
        return questions, None
    except json.JSONDecodeError as e:
        return None, f"JSON parsing error: {e}\n\nFirst 500 characters of response:\n{response[:500]}..."
    except Exception as e:
        return None, f"Unexpected error: {str(e)}\n\nFirst 500 characters of response:\n{response[:500]}..."

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Generated Exam', 0, 1, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.multi_cell(0, 10, title)
        self.ln(5)

    def chapter_body(self, body):
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 10, body)
        self.ln()

def generate_pdf(questions, include_answers=False):
    pdf = PDF()
    pdf.add_page()

    for i, q in enumerate(questions):
        question = f"Q{i+1}: {q['question']}"
        pdf.chapter_title(question)

        choices = "\n".join(q['choices'])
        pdf.chapter_body(choices)

        if include_answers:
            correct_answer = f"Correct answer: {q['correct_answer']}"
            pdf.chapter_body(correct_answer)

            explanation = f"Explanation: {q['explanation']}"
            pdf.chapter_body(explanation)

    return pdf.output(dest="S").encode("latin1")

def main():
    st.title("Exam Creator")
    
    if "app_mode" not in st.session_state:
        st.session_state.app_mode = "Upload PDF & Generate Questions"
    
    # Sidebar Links
    st.sidebar.markdown("## Navigation")
    st.sidebar.write("[Home](https://lernen.streamlit.app)")
    st.sidebar.write("[How to get your API Key](https://youtu.be/NsTAjBdHb1k)")
    st.sidebar.markdown("## License & Contact")
    st.sidebar.write("[License](#)")
    st.sidebar.write("mailto:pietro.rossi@bbw.ch")

    app_mode_options = ["Upload PDF & Generate Questions", "Take the Quiz", "Download as PDF"]
    st.session_state.app_mode = st.sidebar.radio("Choose the app mode", app_mode_options, index=app_mode_options.index(st.session_state.app_mode))
    
    # API Key input
    api_key = st.text_input("Enter your OpenAI API Key:", type="password")
    
    if st.session_state.app_mode == "Upload PDF & Generate Questions":
        pdf_upload_app(api_key)
    elif st.session_state.app_mode == "Take the Quiz":
        if 'mc_test_generated' in st.session_state and st.session_state.mc_test_generated:
            if 'generated_questions' in st.session_state and st.session_state.generated_questions:
                mc_quiz_app()
            else:
                st.warning("No generated questions found. Please upload a PDF and generate questions first.")
        else:
            st.warning("Please upload a PDF and generate questions first.")
    elif st.session_state.app_mode == "Download as PDF":
        download_pdf_app()

def pdf_upload_app(api_key):
    # Content similar to the original upload page with processing
    pass

def mc_quiz_app():
    # Quiz implementation
    pass

def download_pdf_app():
    st.subheader('Download Your Exam as PDF')

    questions = st.session_state.generated_questions

    if questions:
        st.write("Choose the format of the PDF:")
        with_answers = st.radio("Include answers and explanations in the PDF?", ["Without Answers", "With Answers"], index=0)
        include_answers = with_answers == "With Answers"
        
        pdf_bytes = generate_pdf(questions, include_answers=include_answers)
        file_name = "exam_with_answers.pdf" if include_answers else "exam_without_answers.pdf"
        st.download_button(
            label="Download PDF",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf"
        )

if __name__ == '__main__':
    main()
