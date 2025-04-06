import deepl    # https://github.com/DeepLcom/deepl-python
import json
import os
import sys
import re
import time
import textwrap
from dotenv import load_dotenv

"""
JSON Translator with DeepL
--------------------------------
This script translates JSON files from a source directory using DeepL.
It counts words before translation and saves the translated files
in a target directory at the same level.

by Stefan Schmitt, 2025

Usage:
python translate_json_with_deepl.py my_folder EN
"""

class JSONTranslatorDeepL:
    def __init__(self, api_key, simulation=False):
        self.translator = deepl.Translator(api_key)
        self.simulation = simulation
        self.total_char_count = 0

    def supported_source_languages(self):
        """ Returns the supported source languages from the DeepL API """
        try:
            result = self.translator.get_source_languages()
            return [lang.language for lang in result]
        except deepl.exceptions.DeepLException as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

    def is_supported_source_language(self, lang_code):
        """ Checks if the given language code is supported by DeepL """
        return lang_code.upper() in self.supported_source_languages()

    def supported_target_languages(self):
        """ Returns the supported target languages from the DeepL API """
        try:
            result = self.translator.get_target_languages()
            return [lang.code for lang in result]
        except deepl.exceptions.DeepLException as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

    def is_supported_target_language(self, lang_code):
        """ Checks if the given language code is supported by DeepL """
        return lang_code.upper() in self.supported_target_languages()

    def replace_placeholders(self, text):
        """ Replaces placeholders like {{name}} in the text with temporary tokens """
        placeholders = re.findall(r"\{\{.*?\}\}", text)
        temp_tokens = {ph: f"@@{i}@@" for i, ph in enumerate(placeholders)}
        for ph, token in temp_tokens.items():
            text = text.replace(ph, token)
        return text, temp_tokens

    def restore_placeholders(self, text, temp_tokens):
        """ Resets the temporary tokens back to their original placeholders """
        for ph, token in temp_tokens.items():
            text = text.replace(token, ph)
        return text

    def count_words_and_phrases_in_dict(self, data):
        """ Counts the number of phrases (= keys with string values) and words of the phrases in a JSON dictionary recursively """
        phrase_count = 0
        word_count = 0
        if isinstance(data, dict):
            for value in data.values():
                phrases, words = self.count_words_and_phrases_in_dict(value)
                phrase_count += phrases
                word_count += words
        elif isinstance(data, list):
            for item in data:
                phrases, words = self.count_words_and_phrases_in_dict(item)
                phrase_count += phrases
                word_count += words
        elif isinstance(data, str) and data.strip():
            phrase_count += 1
            word_count += len(data.split())
        return phrase_count, word_count

    def translate_dict(self, data, target_lang="EN", context=None):
        """ Translates a JSON dictionary recursively using the DeepL API and counts translated characters """
        if isinstance(data, dict):
            return {key: self.translate_dict(value, target_lang, context) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.translate_dict(item, target_lang, context) for item in data]
        elif isinstance(data, str) and data.strip(): 
            text_with_tokens, tokens = self.replace_placeholders(data)
            if not self.simulation:
                retry_attempts = 5
                timeout = 1 # seconds
                for attempt in range(retry_attempts):
                    try:
                        result = self.translator.translate_text(text_with_tokens, target_lang=target_lang, context=context)
                        translated_text = result.text
                        char_count = result.billed_characters
                        self.total_char_count += char_count
                        source_text = re.sub(r"[\r\n\t]", "", text_with_tokens)
                        target_text = re.sub(r"[\r\n\t]", "", translated_text)
                        print(f"\r {shorten_text(source_text, 50).rjust(50)} → {shorten_text(target_text, 50).ljust(50)}", end="", flush=True)
                        return self.restore_placeholders(translated_text, tokens)
                    except deepl.exceptions.DeepLException as e:
                        print(f"\n❌ Error at DeepL translation: {e}")
                        if attempt < retry_attempts - 1:
                            print(f"🔄 Retrying...in {timeout} second")
                            time.sleep(timeout)             # Wait before retrying
                            timeout = min(timeout * 5, 60)  # Exponential backoff
                        else:
                            print("❌ Error: Maximum retry attempts reached.")
                            return data
            else:
                translated_text = text_with_tokens  # Deactivate translation for testing
                source_text = re.sub(r"[\r\n\t]", "", text_with_tokens)
                target_text = re.sub(r"[\r\n\t]", "", translated_text)
                print(f"\r {shorten_text(source_text, 50).rjust(50)} → {shorten_text(target_text, 50).ljust(50)}", end="", flush=True)
        return data

def get_api_key(env_variable="DEEPL_API_KEY"):
    try:
        load_dotenv()
        api_key = os.getenv(env_variable)
        if not api_key:
            print("❌ Error: DEEPL_API_KEY not found in .env file.")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error: Could not load .env file. {e}")
        sys.exit(1)
    else:
        return api_key

def get_json_indentation(file_path):
    """ Detects the indentation of a JSON file and returns the number of spaces used for indentation """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        print(f"❌ Error: Could not read file '{file_path}'. {e}")
        return 4
    except Exception as e:
        print(f"❌ Error: An unexpected error occurred while reading '{file_path}'. {e}")
        return 4

    indent_counts = []
    
    for line in lines:
        match = re.match(r"^(\s+)", line)               # Checks for leading whitespace
        if match:
            indent_counts.append(len(match.group(1)))   # Length of leading whitespace

    indent_value = min(set(indent_counts))              # Smallest indent value
    return indent_value

def shorten_text(text, max_length=15, placeholder="..."):
    return text[:max_length-len(placeholder)] + placeholder if len(text) > max_length else text

def translate_json_directory(source_directory, target_lang="EN", context=None):

    global simulate

    start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
    print(f"✅ Starting at {start_time}")
    
    translator = JSONTranslatorDeepL(get_api_key(), simulate)

    """ Translates all JSON files in the source directory and saves them in the target directory """
    if not translator.is_supported_target_language(target_lang):
        print(f"❌ Error: The language code '{target_lang}' is not supported by DeepL.")
        return
    if not os.path.exists(source_directory):
        print(f"❌ Error: The source directory '{source_directory}' does not exist.")
        return
    if not os.path.isdir(source_directory):
        print(f"❌ Error: The source directory '{source_directory}' is not a directory.")
        return
    if not os.access(source_directory, os.R_OK):
        print(f"❌ Error: The source directory '{source_directory}' is not readable.")
        return
        
    parent_directory = "./" + os.path.relpath(os.path.join(source_directory, os.pardir))  # Parent directory
    target_directory = os.path.join(parent_directory, target_lang.lower())  # Target directory at the same level
    
    try:
        os.makedirs(target_directory, exist_ok=True)  # Create target directory if it doesn't exist
    except OSError as e:
        print(f"❌ Error: Could not create target directory '{target_directory}'. {e}")
        return
    
    total_word_count = 0
    total_phrase_count = 0
    file_count = 0

    for filename in os.listdir(source_directory):
        if filename.endswith(".json"):

            input_file = os.path.join(source_directory, filename)
            output_file = os.path.join(target_directory, filename)

            try:
                with open(input_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except OSError as e:
                print(f"❌ Error: Could not read file '{input_file}'. {e}")
                continue
            except json.JSONDecodeError as e:
                print(f"❌ Error: Could not decode JSON in file '{input_file}'. {e}")
                continue
            except Exception as e:
                print(f"❌ Error: An unexpected error occurred while reading '{input_file}'. {e}")
                continue
            if not isinstance(data, dict):
                print(f"❌ Error: The file '{input_file}' does not contain a valid JSON object.")
                continue

            file_count += 1
            translated_data = translator.translate_dict(data, target_lang, context)
            print(f"\r", end="", flush=True)

            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(translated_data, f, ensure_ascii=False, indent=get_json_indentation(input_file))
            except OSError as e:
                print(f"❌ Error: Could not write to file '{output_file}'. {e}")
                continue
            
            phrase_count, word_count = translator.count_words_and_phrases_in_dict(translated_data)

            print(f"✅ Translated: {input_file} → {output_file} | Words: {word_count} | Phrases: {phrase_count}")
            total_word_count += word_count
            total_phrase_count += phrase_count
    
    if file_count == 0:
        print("❌ Error: No JSON file found in the source directory.")
    else:
        print(f"✅ Total count of characters: {translator.total_char_count} | Total count of words is {total_word_count} | Total count of phrases is {total_phrase_count} | Files: {file_count}")
    end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
    print(f"✅ Finishing at {end_time}")


# Set the simulation mode to True for testing
simulate = True

if __name__ == "__main__":
    if sys.gettrace():  # Check if running in debugger
        source_directory = "./Translations/en"
        target_language_code = "DE"
        context = "The context of the translation is a software application for the railway industry."
    else:
        if len(sys.argv) < 3 or len(sys.argv) > 4:
            print("❌ Error: Please enter the source directory and the language code!")
            print("💡 Usage: python3 translate_json_with_deepl.py <source_directory> <target_language_code> [<context string>]")
            sys.exit(1)
        else:
            source_directory = sys.argv[1]
            target_language_code = sys.argv[2]
            context = sys.argv[3] if len(sys.argv) == 4 else None

    translate_json_directory(source_directory, target_language_code, context=context)
