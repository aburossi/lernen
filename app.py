import streamlit as st
import time
from openai import OpenAI
import json
from PyPDF2 import PdfReader
from fpdf import FPDF

# Set page config
st.set_page_config(page_title="SmartExam Creator", page_icon="📝")

__version__ = "1.1.0"

# Main app functions
def stream_llm_response(messages, model_params, api_key):
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model_params["model"] if "model" in model_params else "gpt-4",
        messages=messages,
        temperature=model_params["temperature"] if "temperature" in model_params else 0.3,
        max_tokens=4096,
    )
    return response.choices[0].message.content

def extract_text_from_pdf(pdf_file):
    pdf_reader = PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def summarize_text(text, api_key):
    prompt = "Please summarize the following text to be concise and to the point:\n\n" + text
    messages = [{"role": "user", "content": prompt}]
    summary = stream_llm_response(messages, model_params={"model": "gpt-3.5-turbo", "temperature": 0.3}, api_key=api_key)
    return summary

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
        "You are a professor in the field of Computational System Biology. Your task is to create a Master-level "
        "multiple-choice exam based on the provided PDF content. Create 30 realistic exam questions covering the "
        "entire content. Each question should be directly related to the information in the PDF."
    )
    user_prompt = (
        "Using the following content from the uploaded PDF, create multiple-choice and single-choice questions. "
        "Ensure that each question is based on the information provided in the PDF content. "
        "Mark questions appropriately so that students know how many options to select. "
        "Provide the output in JSON format with the following structure: "
        "[{'question': '...', 'choices': ['...'], 'correct_answer': '...', 'explanation': '...'}, ...]. "
        "Ensure the JSON is valid and properly formatted.\n\nPDF Content:\n\n"
    ) + content_text

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        response = stream_llm_response(messages, model_params={"model": "gpt-3.5-turbo", "temperature": 0.3}, api_key=api_key)
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

def generate_pdf(questions):
    pdf = PDF()
    pdf.add_page()

    for i, q in enumerate(questions):
        question = f"Q{i+1}: {q['question']}"
        pdf.chapter_title(question)

        choices = "\n".join(q['choices'])
        pdf.chapter_body(choices)

        correct_answer = f"Correct answer: {q['correct_answer']}"
        pdf.chapter_body(correct_answer)

        explanation = f"Explanation: {q['explanation']}"
        pdf.chapter_body(explanation)

    return pdf.output(dest="S").encode("latin1")

def main():
    st.title("SmartExam Creator")
    
    if "app_mode" not in st.session_state:
        st.session_state.app_mode = "Upload PDF & Generate Questions"
    
    app_mode_options = ["Upload PDF & Generate Questions", "Take the Quiz", "Download as PDF"]
    st.session_state.app_mode = st.sidebar.selectbox("Choose the app mode", app_mode_options, index=app_mode_options.index(st.session_state.app_mode))
    
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
    st.subheader("Upload Your Lecture - Create Your Test Exam")
    st.write("Show Us the Slides and We do the Rest")

    content_text = ""
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    uploaded_pdf = st.file_uploader("Upload a PDF document", type=["pdf"])
    if uploaded_pdf and api_key:
        pdf_text = extract_text_from_pdf(uploaded_pdf)
        content_text += pdf_text
        st.success("PDF content added to the session.")
        
        # Display a sample of the extracted text for verification
        st.subheader("Sample of extracted PDF content:")
        st.text(content_text[:500] + "...")  # Display first 500 characters
    
        if len(content_text) > 3000:
            content_text = summarize_text(content_text, api_key)
            st.subheader("Summarized content:")
            st.text(content_text[:500] + "...")  # Display first 500 characters of summarized content

        st.info("Generating the exam from the uploaded content. It will take just a minute...")
        chunks = chunk_text(content_text)
        questions = []
        for chunk in chunks:
            response, error = generate_mc_questions(chunk, api_key)
            if error:
                st.error(f"Error generating questions: {error}")
                break
            parsed_questions, parse_error = parse_generated_questions(response)
            if parse_error:
                st.error(parse_error)
                st.text("Full response:")
                st.text(response)
                break
            if parsed_questions:
                questions.extend(parsed_questions)
        if questions:
            st.session_state.generated_questions = questions
            st.session_state.content_text = content_text
            st.session_state.mc_test_generated = True
            st.success("The game has been successfully created! Switch the Sidebar Panel to solve the exam.")
            
            # Display a sample question for verification
            st.subheader("Sample generated question:")
            st.json(questions[0])
            
            time.sleep(2)
            st.session_state.app_mode = "Take the Quiz"
            st.rerun()
        else:
            st.error("No questions were generated. Please check the error messages above and try again.")
    elif not api_key:
        st.warning("Please enter your OpenAI API key.")
    else:
        st.warning("Please upload a PDF to generate the interactive exam.")


def submit_answer(i, quiz_data):
    user_choice = st.session_state[f"user_choice_{i}"]
    st.session_state.answers[i] = user_choice
    if user_choice == quiz_data['correct_answer']:
        st.session_state.feedback[i] = ("Correct", quiz_data.get('explanation', 'No explanation available'))
        st.session_state.correct_answers += 1
    else:
        st.session_state.feedback[i] = ("Incorrect", quiz_data.get('explanation', 'No explanation available'), quiz_data['correct_answer'])

def mc_quiz_app():
    st.subheader('Multiple Choice Game')
    st.write('Here is always one correct answer per question')

    questions = st.session_state.generated_questions

    if questions:
        if 'answers' not in st.session_state:
            st.session_state.answers = [None] * len(questions)
            st.session_state.feedback = [None] * len(questions)
            st.session_state.correct_answers = 0

        for i, quiz_data in enumerate(questions):
            st.markdown(f"### Question {i+1}: {quiz_data['question']}")

            if st.session_state.answers[i] is None:
                user_choice = st.radio("Choose an answer:", quiz_data['choices'], key=f"user_choice_{i}")
                st.button(f"Submit your answer {i+1}", key=f"submit_{i}", on_click=submit_answer, args=(i, quiz_data))
            else:
                st.radio("Choose an answer:", quiz_data['choices'], key=f"user_choice_{i}", index=quiz_data['choices'].index(st.session_state.answers[i]), disabled=True)
                if st.session_state.feedback[i][0] == "Correct":
                    st.success(st.session_state.feedback[i][0])
                else:
                    st.error(f"{st.session_state.feedback[i][0]} - Correct answer: {st.session_state.feedback[i][2]}")
                st.markdown(f"Explanation: {st.session_state.feedback[i][1]}")

        if all(answer is not None for answer in st.session_state.answers):
            score = st.session_state.correct_answers
            total_questions = len(questions)
            st.write(f"""
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh;">
                    <h1 style="font-size: 3em; color: gold;">🏆</h1>
                    <h1>Your Score: {score}/{total_questions}</h1>
                </div>
            """, unsafe_allow_html=True)

def download_pdf_app():
    st.subheader('Download Your Exam as PDF')

    questions = st.session_state.generated_questions

    if questions:
        for i, q in enumerate(questions):
            st.markdown(f"### Q{i+1}: {q['question']}")
            for choice in q['choices']:
                st.write(choice)
            st.write(f"**Correct answer:** {q['correct_answer']}")
            st.write(f"**Explanation:** {q['explanation']}")
            st.write("---")

        pdf_bytes = generate_pdf(questions)
        st.download_button(
            label="Download PDF",
            data=pdf_bytes,
            file_name="generated_exam.pdf",
            mime="application/pdf"
        )

if __name__ == '__main__':
    main()
