import time
import json
import os
import argparse
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from datetime import datetime


class KokoroTTSTest:
    """
    Test automation for Kokoro TTS web application using Selenium.
    Implements test techniques like Equivalence Partitioning and Boundary Value Analysis.
    """
    
    def __init__(self, base_url="http://localhost:5000", headless=True, timeout=120):
        """Initialize the test automation with configurable settings."""
        self.base_url = base_url
        self.timeout = timeout  # FIXED: Increased default timeout
        self.results = []
        self.tested_combinations = set()  # Track already tested combinations
        self.screenshot_dir = "test_screenshots"
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
        # Setup WebDriver
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless")
        options.add_argument("start-maximized")
        options.add_argument("--window-size=1920,1080")
        # to supress the error messages/logs
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        # Add additional options to make browser more stable
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-extensions")
        
        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.set_page_load_timeout(timeout)
            # Set script timeout for JavaScript execution
            self.driver.set_script_timeout(timeout)
        except Exception as e:
            print(f"Error initializing WebDriver: {str(e)}")
            raise
        
    def __del__(self):
        """Clean up resources when object is destroyed."""
        try:
            if hasattr(self, 'driver'):
                self.driver.quit()
        except Exception as e:
            print(f"Error cleaning up WebDriver: {str(e)}")
    
    def take_screenshot(self, name):
        """Take a screenshot for debugging purposes."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.screenshot_dir}/{name}_{timestamp}.png"
            self.driver.save_screenshot(filename)
            print(f"Screenshot saved to {filename}")
        except Exception as e:
            print(f"Error taking screenshot: {str(e)}")
    
    def wait_for_element(self, by, value, timeout=None, retries=2):
        """Wait for element to be visible with custom timeout and retry mechanism."""
        if timeout is None:
            timeout = self.timeout
            
        for attempt in range(retries + 1):
            try:
                return WebDriverWait(self.driver, timeout).until(
                    EC.visibility_of_element_located((by, value))
                )
            except TimeoutException:
                if attempt < retries:
                    print(f"Timeout waiting for element: {by}={value}. Retry {attempt+1}/{retries}")
                    self.take_screenshot(f"timeout_{by}_{value}")
                    # Refresh the page and try again
                    self.driver.refresh()
                    time.sleep(2)  # Give page time to reload
                else:
                    print(f"Final timeout waiting for element: {by}={value}")
                    self.take_screenshot(f"final_timeout_{by}_{value}")
                    raise
            except StaleElementReferenceException:
                if attempt < retries:
                    print(f"Stale element: {by}={value}. Retry {attempt+1}/{retries}")
                    time.sleep(1)  # Small wait before retry
                else:
                    raise
    
    def safe_select_by_visible_text(self, select_element, text, max_attempts=3):
        """Safely select an option by text with retry mechanism."""
        select = Select(select_element)
        for attempt in range(max_attempts):
            try:
                select.select_by_visible_text(text)
                time.sleep(0.5)  # Wait for the selection to take effect
                # Verify selection was successful
                selected_option = select.first_selected_option
                if selected_option.text == text:
                    return True
                else:
                    print(f"Selection verification failed. Expected: {text}, Got: {selected_option.text}")
            except Exception as e:
                print(f"Selection error (attempt {attempt+1}/{max_attempts}): {str(e)}")
                time.sleep(1)
                
        # If we get here, all attempts failed
        self.take_screenshot(f"select_failed_{text}")
        return False
    
    def wait_for_status(self, expected_status=None, max_wait_time=None):
        """
        Wait for status element to show completion and return status info.
        
        Args:
            expected_status: Expected status class to verify (for assertion)
            max_wait_time: Maximum time to wait for status change
            
        Returns:
            tuple: (status_text, status_class, elapsed_time)
        """
        if max_wait_time is None:
            max_wait_time = self.timeout
            
        start_time = time.time()
        status_elem = self.wait_for_element(By.ID, "status")
        
        # Wait for status to change from "loading"
        while "loading" in status_elem.get_attribute("class") and time.time() - start_time < max_wait_time:
            time.sleep(0.5)
            try:
                status_elem = self.driver.find_element(By.ID, "status")
            except (NoSuchElementException, StaleElementReferenceException):
                # If element becomes stale, find it again
                status_elem = self.wait_for_element(By.ID, "status")
            
        end_time = time.time()
        
        try:
            status_text = status_elem.text
            status_class = status_elem.get_attribute("class")
        except (NoSuchElementException, StaleElementReferenceException):
            # Final attempt to get status
            status_elem = self.wait_for_element(By.ID, "status")
            status_text = status_elem.text
            status_class = status_elem.get_attribute("class")
            
        # Assert if expected status is provided (test validation)
        if expected_status and expected_status not in status_class:
            self.take_screenshot(f"status_assertion_failed")
            assert expected_status in status_class, f"Expected status '{expected_status}' but got '{status_class}'"
            
        elapsed_time = end_time - start_time
        return status_text, status_class, elapsed_time
    
    def get_voices_by_language(self):
        """
        Get the voices by language from the page with better error handling.
        """
        try:
            self.wait_for_element(By.ID, "language-select")
            result = self.driver.execute_script("return JSON.stringify(voicesByLanguage)")
            if not result:
                raise ValueError("voicesByLanguage is empty or undefined")
            return json.loads(result)
        except Exception as e:
            print(f"Error getting voices data: {str(e)}")
            self.take_screenshot("voices_data_error")
            
            # Fallback: Try to build the voices structure ourselves
            voices_by_language = {}
            
            # Get all language options
            language_select = self.driver.find_element(By.ID, "language-select")
            select = Select(language_select)
            options = select.options
            
            for option in options:
                lang = option.text
                voices_by_language[lang] = []
                
                # Select this language to populate voice options
                select.select_by_visible_text(lang)
                time.sleep(1)  # Wait for voice options to update
                
                # Get voice options
                voice_select = self.driver.find_element(By.ID, "voice-select")
                voice_options = Select(voice_select).options
                
                for voice_option in voice_options:
                    # Parse gender from text (typically has format "NAME (Male/Female)")
                    name = voice_option.text
                    gender = "m" if "(Male)" in name else "f"
                    
                    voices_by_language[lang].append({
                        "name": name,
                        "code": voice_option.get_attribute("value"),
                        "gender": gender
                    })
            
            return voices_by_language
    
    def test_generate_speech(self, language, voice, text, equivalence_partition=None):
        """
        Test speech generation for a specific language, voice and text.
        
        Args:
            language: The language to select
            voice: Dictionary with voice information (name, code, gender)
            text: The text to convert to speech
            equivalence_partition: For documenting which test partition this belongs to
            
        Returns:
            dict: Test result data
        """
        # Create combination ID to prevent duplicate tests
        combination_id = f"{language}_{voice['code']}_{len(text)}"
        
        # Skip if this exact combination was already tested
        if combination_id in self.tested_combinations and equivalence_partition != "warmup":
            print(f"Skipping duplicate test: {language} - {voice['name']} with {len(text)} chars")
            return None
            
        self.tested_combinations.add(combination_id)
        
        try:
            # Select language - FIXED: More robust selection with verification
            language_select = self.driver.find_element(By.ID, "language-select")
            selection_success = self.safe_select_by_visible_text(language_select, language)
            if not selection_success:
                raise Exception(f"Failed to select language: {language}")
                
            # Wait for voice options to update
            time.sleep(2)
            
            # Select voice - FIXED: More robust selection
            voice_select = self.driver.find_element(By.ID, "voice-select")
            voice_select_obj = Select(voice_select)
            
            # Try to find the voice by value first
            try:
                voice_select_obj.select_by_value(voice["code"])
            except NoSuchElementException:
                # If failed, try to find a voice with a similar name
                found_match = False
                for option in voice_select_obj.options:
                    if voice["name"] in option.text or voice["code"] in option.get_attribute("value"):
                        voice_select_obj.select_by_value(option.get_attribute("value"))
                        voice["code"] = option.get_attribute("value")  # Update the code
                        found_match = True
                        break
                
                if not found_match:
                    # If still can't find, just select the first voice
                    voice_select_obj.select_by_index(0)
                    if voice_select_obj.options:
                        voice["code"] = voice_select_obj.options[0].get_attribute("value")
            
            time.sleep(1)  # Wait after selection
            
            # Enter text - apply boundary value analysis for text input
            text_area = self.driver.find_element(By.ID, "text-area")
            text_area.clear()
            text_area.send_keys(text)
            
            # Click generate button and measure time
            generate_btn = self.driver.find_element(By.ID, "generate-btn")
            generate_start_time = time.time()
            generate_btn.click()
            
            # FIXED: Add more wait time for processing
            time.sleep(2)
            
            # Wait for status to complete
            status_text, status_class, elapsed_time = self.wait_for_status(max_wait_time=self.timeout * 2)
            
            # Take a screenshot after generation completes
            self.take_screenshot(f"after_generation_{language}_{voice['code']}")
            
            # Track whether we got an error message related to TensorFlow
            tensorflow_error = False
            try:
                # Check if there are error messages in the browser console
                logs = self.driver.get_log('browser')
                for log in logs:
                    if "tensor" in log.get('message', '').lower():
                        tensorflow_error = True
                        print(f"TensorFlow error detected: {log['message']}")
            except:
                pass  # Browser log access not available
            
            # Assert audio player is visible when successful
            audio_visible = False
            try:
                # FIXED: Wait for audio container to become visible
                if "success" in status_class:
                    try:
                        audio_container = WebDriverWait(self.driver, 5).until(
                            EC.visibility_of_element_located((By.ID, "audio-container"))
                        )
                        audio_visible = "hidden" not in audio_container.get_attribute("class")
                    except TimeoutException:
                        self.take_screenshot(f"audio_container_not_visible")
                        print("Audio container not visible despite success status")
                else:
                    # Check if it exists anyway
                    try:
                        audio_container = self.driver.find_element(By.ID, "audio-container")
                        audio_visible = "hidden" not in audio_container.get_attribute("class")
                    except NoSuchElementException:
                        audio_visible = False
                
                # Assert that audio is visible if status is success
                if "success" in status_class and not audio_visible:
                    self.take_screenshot(f"audio_assertion_failed")
                    print("Warning: Audio player should be visible when generation is successful")
            except NoSuchElementException:
                if "success" in status_class:
                    self.take_screenshot(f"audio_container_missing")
                    print("Warning: Audio container not found despite successful status")
            
            # Record results
            result = {
                "language": language,
                "voice_name": voice["name"],
                "voice_code": voice["code"],
                "voice_gender": voice["gender"],
                "text_length": len(text),
                "status_text": status_text,
                "status_class": status_class.replace("status ", ""),
                "generation_time_seconds": elapsed_time,
                "audio_generated": audio_visible,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "test_partition": equivalence_partition,
                "tensorflow_error": tensorflow_error
            }
            
            # Only print for non-warmup runs
            if equivalence_partition != "warmup":
                print(f"Tested {language} - {voice['name']}: {result['status_class']} in {elapsed_time:.2f}s")
            
            return result
            
        except Exception as e:
            # Take error screenshot
            self.take_screenshot(f"error_{language}_{voice['code']}")
            
            # Record error
            result = {
                "language": language,
                "voice_name": voice["name"],
                "voice_code": voice["code"],
                "voice_gender": voice["gender"],
                "text_length": len(text),
                "status_text": f"Test error: {str(e)}",
                "status_class": "error",
                "generation_time_seconds": 0,
                "audio_generated": False,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "test_partition": equivalence_partition,
                "error": str(e)
            }
            # Only print for non-warmup runs
            if equivalence_partition != "warmup":
                print(f"Error testing {language} - {voice['name']}: {str(e)}")
            return result
    
    def perform_warmup_run(self, voices_by_language):
        """
        Perform a warmup run to load models before actual testing.
        This helps eliminate the first-load time bias.
        
        Args:
            voices_by_language: Dictionary of voices by language
        """
        print("Performing warmup run to load models (results will not be recorded)...")
        
        # Select a voice from each language for warmup
        for language, voices in voices_by_language.items():
            if voices:
                # Navigate to the app
                self.driver.get(self.base_url)
                try:
                    self.wait_for_element(By.ID, "language-select")
                    
                    # Do a warmup run with a short text
                    warmup_text = "This is a warmup test."
                    self.test_generate_speech(
                        language,
                        voices[0],  # Use first voice for each language
                        warmup_text,
                        equivalence_partition="warmup"
                    )
                    print(f"Warmup complete for {language} - {voices[0]['name']}")
                    
                    # Only do one warmup per language
                    break
                except Exception as e:
                    print(f"Warmup failed for {language}: {str(e)}")
                    self.take_screenshot(f"warmup_failed_{language}")
                
                # Clear the tested_combinations set to not affect real tests
                self.tested_combinations.clear()
    
    def run_equivalence_partition_tests(self, randomize=True):
        """
        Run tests using equivalence partitioning technique.
        
        This groups test cases into partitions:
        1. Language families (European, Asian, etc.)
        2. Voice genders (male, female)
        3. Text lengths (short, medium, long)
        
        Args:
            randomize: Whether to randomize the test order to avoid bias
        """
        # Navigate to the app
        try:
            self.driver.get(self.base_url)
            self.wait_for_element(By.ID, "language-select")
        except Exception as e:
            print(f"Failed to load initial page: {str(e)}")
            self.take_screenshot("initial_page_load_failure")
            raise
        
        # Get voices by language from the page - FIXED: More robust implementation
        voices_by_language = self.get_voices_by_language()
        
        # Perform warmup run first to load models
        self.perform_warmup_run(voices_by_language)
        
        # Define language groups for equivalence partitioning
        language_groups = {
            "European": ["English (US)", "English (UK)", "French", "Italian", "Spanish", "Portuguese (Brazil)"],
        }
        
        # Define text samples by length (boundary value analysis)
        text_samples = {
            "short": {  # Short text (< 10 words)
                "English (US)": "Hello world.",
                "English (UK)": "Hello world.",
                "Spanish": "Hola mundo.",
                "French": "Bonjour le monde.",
                "Italian": "Ciao mondo.",
                "Portuguese (Brazil)": "Olá mundo."
            },
            "medium": {  # Medium text (10-50 words)
                "English (US)": "This is a test of the Kokoro Text-to-Speech system. We are generating audio from text input to validate the functionality.",
                "English (UK)": "This is a test of the Kokoro Text-to-Speech system. We are generating audio from text input to validate the functionality.",
                "Spanish": "Esta es una prueba del sistema Kokoro de texto a voz. Estamos generando audio a partir de texto para validar la funcionalidad.",
                "French": "Ceci est un test du système de synthèse vocale Kokoro. Nous générons de l'audio à partir d'entrée de texte pour valider les fonctionnalités.",
                "Italian": "Questo è un test del sistema di sintesi vocale Kokoro. Stiamo generando audio dall'input di testo per convalidare la funzionalità.",
                "Portuguese (Brazil)": "Este é um teste do sistema Kokoro de texto para fala. Estamos gerando áudio a partir da entrada de texto para validar a funcionalidade."
            },
            "long": {  # Long text (> 100 words)
                # For each language, create a long text by repeating the medium text
                "English (US)": "This is a test of the Kokoro Text-to-Speech system. We are generating audio from text input to validate the functionality. " * 5,
                "English (UK)": "This is a test of the Kokoro Text-to-Speech system. We are generating audio from text input to validate the functionality. " * 5,
                "Spanish": "Esta es una prueba del sistema Kokoro de texto a voz. Estamos generando audio a partir de texto para validar la funcionalidad. " * 5,
                "French": "Ceci est un test du système de synthèse vocale Kokoro. Nous générons de l'audio à partir d'entrée de texte pour valider les fonctionnalités. " * 5,
                "Italian": "Questo è un test del sistema di sintesi vocale Kokoro. Stiamo generando audio dall'input di testo per convalidare la funzionalità. " * 5,
                "Portuguese (Brazil)": "Este é um teste do sistema Kokoro de texto para fala. Estamos gerando áudio a partir da entrada de texto para validar a funcionalidade. " * 5
            },
            "boundary": {  # Edge case with special characters, numbers, etc.
                "English (US)": "Test with numbers (123) & special chars: !@#$%. Is it handled properly?",
                "English (UK)": "Test with numbers (123) & special chars: !@#$%. Is it handled properly?",
                "Spanish": "Prueba con números (123) y caracteres especiales: !@#$%. ¿Se maneja correctamente?",
                "French": "Test avec des chiffres (123) et des caractères spéciaux: !@#$%. Est-ce bien géré?",
                "Italian": "Test con numeri (123) e caratteri speciali: !@#$%. È gestito correttamente?",
                "Portuguese (Brazil)": "Teste com números (123) e caracteres especiais: !@#$%. É tratado corretamente?"
            }
        }
        
        # Build test cases list
        test_cases = []
        
        # For each language group
        for group_name, languages in language_groups.items():
            # Test representative languages from this group
            for language in languages:
                if language not in voices_by_language:
                    continue
                    
                # For gender partition, test at least one male and one female voice if available
                voices = voices_by_language[language]
                male_voices = [v for v in voices if v["gender"] == "m"]
                female_voices = [v for v in voices if v["gender"] == "f"]
                
                test_voices = []
                if male_voices:
                    test_voices.append(male_voices[0])
                if female_voices:
                    test_voices.append(female_voices[0])
                
                # For each selected voice, test different text lengths
                for voice in test_voices:
                    # Test all text length partitions for each voice
                    for text_type, texts in text_samples.items():
                        if language in texts:
                            # Build partition identifier
                            partition = f"{group_name}_lang.{voice['gender']}_gender.{text_type}_text"
                            
                            # Add test case to list
                            test_cases.append({
                                "language": language,
                                "voice": voice,
                                "text": texts[language],
                                "partition": partition
                            })
        
        # Randomize test order if requested
        if randomize:
            random.shuffle(test_cases)
            
        # Run test cases
        results = []
        for idx, test_case in enumerate(test_cases):
            print(f"Running test {idx+1}/{len(test_cases)}: {test_case['language']} - {test_case['voice']['name']} - {test_case['partition']}")
            
            # Reload page for each test to ensure clean state
            try:
                self.driver.get(self.base_url)
                self.wait_for_element(By.ID, "language-select")
            except Exception as e:
                print(f"Failed to reload page: {str(e)}")
                self.take_screenshot(f"page_reload_failure_{idx}")
                continue  # Skip this test but continue with others
            
            result = self.test_generate_speech(
                test_case["language"], 
                test_case["voice"], 
                test_case["text"],
                equivalence_partition=test_case["partition"]
            )
            
            if result:  # Skip if None (duplicate test)
                results.append(result)
        
        return results
    
    def run_boundary_value_tests(self):
        """
        Run tests focused on boundary values:
        - Empty text
        - Very short text (1 character)
        - Very long text (near limits)
        - Text with special characters
        """
        # Navigate to the app
        try:
            self.driver.get(self.base_url)
            self.wait_for_element(By.ID, "language-select")
        except Exception as e:
            print(f"Failed to load initial page for boundary tests: {str(e)}")
            self.take_screenshot("boundary_initial_page_load_failure")
            raise
        
        # Get voices by language from the page
        voices_by_language = self.get_voices_by_language()
        
        # Choose one language for boundary testing
        test_language = "English (US)"
        if test_language not in voices_by_language or not voices_by_language[test_language]:
            for lang in voices_by_language:
                if voices_by_language[lang]:
                    test_language = lang
                    break
        
        # Choose one voice for boundary testing
        test_voice = voices_by_language[test_language][0]
        
        # Define boundary test cases
        boundary_tests = [
            {
                "name": "empty_text",
                "text": "",
                "description": "Empty text input (boundary: minimum length)"
            },
            {
                "name": "single_char",
                "text": "A",
                "description": "Single character (boundary: minimal valid input)"
            },
            {
                "name": "very_long",
                "text": "This is a test. " * 100,
                "description": "Very long text (boundary: approaching maximum length)"
            },
            {
                "name": "special_chars",
                "text": "!@#$%^&*()_+{}|:<>?~`-=[]\\;',./",
                "description": "Only special characters (boundary: character types)"
            },
            {
                "name": "numbers_only",
                "text": "12345678901234567890",
                "description": "Only numbers (boundary: character types)"
            },
            {
                "name": "mixed_extremes",
                "text": "A" + ("1" * 50) + "!@#$%^&*()",
                "description": "Mixed extreme values (boundary: combined extremes)"
            }
        ]
        
        results = []
        
        # Run each boundary test
        for idx, test in enumerate(boundary_tests):
            print(f"Running boundary test {idx+1}/{len(boundary_tests)}: {test['name']}")
            
            # Reload page for each test
            try:
                self.driver.get(self.base_url)
                self.wait_for_element(By.ID, "language-select")
            except Exception as e:
                print(f"Failed to reload page for boundary test: {str(e)}")
                self.take_screenshot(f"boundary_page_reload_failure_{test['name']}")
                continue  # Skip this test but continue with others
            
            result = self.test_generate_speech(
                test_language,
                test_voice,
                test["text"],
                equivalence_partition=f"boundary_{test['name']}"
            )
            
            if result:  # Skip if None (duplicate test)
                # Add boundary test metadata
                result["boundary_test"] = test["name"]
                result["boundary_description"] = test["description"]
                results.append(result)
            
        return results
    
    def run_all_tests(self, randomize=True):
        """
        Run all tests including equivalence partitioning and boundary value tests.
        
        Args:
            randomize: Whether to randomize test order
        """
        print("\n=== Starting Equivalence Partition Tests ===")
        try:
            equivalence_results = self.run_equivalence_partition_tests(randomize=randomize)
        except Exception as e:
            print(f"Error during equivalence partition tests: {str(e)}")
            self.take_screenshot("equivalence_tests_error")
            equivalence_results = []
        
        print("\n=== Starting Boundary Value Tests ===")
        try:
            boundary_results = self.run_boundary_value_tests()
        except Exception as e:
            print(f"Error during boundary value tests: {str(e)}")
            self.take_screenshot("boundary_tests_error")
            boundary_results = []
        
        all_results = equivalence_results + boundary_results
        self.results = all_results
        
        # Save results to JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("test_results", exist_ok=True)
        filename = f"test_results/kokoro_tts_test_results_{timestamp}.json"
        
        # Add test summary data
        summary = {
            "total_tests": len(all_results),
            "success_count": sum(1 for r in all_results if "success" in r.get("status_class", "")),
            "error_count": sum(1 for r in all_results if "error" in r.get("status_class", "")),
            "test_timestamp": timestamp,
            "test_results": all_results
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {filename}")
        
        return all_results
    
    def visualize_results(self, output_dir="test_results"):
        """
        Create visualizations of test results using matplotlib and seaborn.
        
        Args:
            output_dir: Directory to save visualization images
        """
        if not self.results:
            print("No results to visualize")
            return
            
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert results to DataFrame
        df = pd.DataFrame(self.results)
        
        # Add success column
        df['success'] = df['status_class'].apply(lambda x: 1 if 'success' in x else 0)
        
        # Generate timestamp for filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Figure 1: Generation time by language
        plt.figure(figsize=(12, 6))
        sns.set_style("whitegrid")
        
        # Group by language and calculate average generation time
        lang_times = df.groupby('language')['generation_time_seconds'].mean().sort_values(ascending=False)
        
        ax = sns.barplot(x=lang_times.index, y=lang_times.values)
        plt.title('Average Generation Time by Language', fontsize=15)
        plt.ylabel('Time (seconds)', fontsize=12)
        plt.xlabel('Language', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        
        # Add values on top of bars
        for i, v in enumerate(lang_times.values):
            ax.text(i, v + 0.1, f"{v:.2f}s", ha='center', fontsize=9)
            
        plt.tight_layout()
        plt.savefig(f"{output_dir}/generation_time_by_language_{timestamp}.png", dpi=300)
        plt.close()
        
        # Figure 2: Success rate by language
        plt.figure(figsize=(12, 6))
        
        # Group by language and calculate success rate
        success_rate = df.groupby('language')['success'].mean() * 100
        
        ax = sns.barplot(x=success_rate.index, y=success_rate.values)
        plt.title('Success Rate by Language (%)', fontsize=15)
        plt.ylabel('Success Rate (%)', fontsize=12)
        plt.xlabel('Language', fontsize=12)
        plt.ylim(0, 105) # To leave room for annotations
        plt.xticks(rotation=45, ha='right')
        
        # Add values on top of bars
        for i, v in enumerate(success_rate.values):
            ax.text(i, v + 1, f"{v:.1f}%", ha='center', fontsize=9)
            
        plt.tight_layout()
        plt.savefig(f"{output_dir}/success_rate_by_language_{timestamp}.png", dpi=300)
        plt.close()
        
        # Figure 3: Text length vs. generation time scatter plot
        plt.figure(figsize=(10, 6))
        
        # Filter only successful generations for this plot
        successful_df = df[df['success'] == 1]
        
        if not successful_df.empty:
            # Create scatter plot with regression line
            sns.regplot(x='text_length', y='generation_time_seconds', data=successful_df, 
                    scatter_kws={'alpha':0.5}, line_kws={'color':'red'})
            
            plt.title('Text Length vs. Generation Time', fontsize=15)
            plt.xlabel('Text Length (characters)', fontsize=12)
            plt.ylabel('Generation Time (seconds)', fontsize=12)
            
            plt.tight_layout()
            plt.savefig(f"{output_dir}/text_length_vs_generation_time_{timestamp}.png", dpi=300)
            plt.close()
        
        # Figure 4: Generation time by voice gender
        plt.figure(figsize=(10, 6))
        
        # Group by gender
        gender_times = df.groupby('voice_gender')['generation_time_seconds'].mean()
        
        ax = sns.barplot(x=gender_times.index, y=gender_times.values)
        plt.title('Average Generation Time by Voice Gender', fontsize=15)
        plt.ylabel('Time (seconds)', fontsize=12)
        plt.xlabel('Voice Gender', fontsize=12)
        plt.xticks([0, 1], ['Male', 'Female'])
        
        # Add values on top of bars
        for i, v in enumerate(gender_times.values):
            ax.text(i, v + 0.1, f"{v:.2f}s", ha='center', fontsize=9)
            
        plt.tight_layout()
        plt.savefig(f"{output_dir}/generation_time_by_gender_{timestamp}.png", dpi=300)
        plt.close()
        
        # Figure 5: Success rate for boundary tests
        plt.figure(figsize=(10, 6))
        
        # Filter boundary tests
        boundary_df = df[df['test_partition'].str.startswith('boundary_', na=False)]
        
        if not boundary_df.empty:
            # Create custom order for boundary tests
            ordered_tests = ['boundary_empty_text', 'boundary_single_char', 
                           'boundary_special_chars', 'boundary_numbers_only', 
                           'boundary_mixed_extremes', 'boundary_very_long']
            
            # Filter only existing tests
            ordered_tests = [t for t in ordered_tests if t in boundary_df['test_partition'].values]
            
            # Group by test name and calculate success rate
            boundary_success = boundary_df.groupby('test_partition')['success'].mean() * 100
            
            # Reindex to get custom order
            if ordered_tests:
                boundary_success = boundary_success.reindex(ordered_tests)
            
            ax = sns.barplot(x=boundary_success.index, y=boundary_success.values)
            plt.title('Success Rate for Boundary Tests (%)', fontsize=15)
            plt.ylabel('Success Rate (%)', fontsize=12)
            plt.xlabel('Boundary Test', fontsize=12)
            plt.ylim(0, 105)
            plt.xticks(rotation=45, ha='right')
            
            # Add values on top of bars
            for i, v in enumerate(boundary_success.values):
                ax.text(i, v + 1, f"{v:.1f}%", ha='center', fontsize=9)
                
            plt.tight_layout()
            plt.savefig(f"{output_dir}/boundary_tests_success_rate_{timestamp}.png", dpi=300)
            plt.close()
        
        # Generate a summary report plot
        plt.figure(figsize=(12, 8))
        
        # Create a text summary
        summary_text = (
            f"Kokoro TTS Test Summary\n"
            f"======================\n\n"
            f"Total Tests: {len(df)}\n"
            f"Overall Success Rate: {df['success'].mean()*100:.1f}%\n"
            f"Average Generation Time: {df['generation_time_seconds'].mean():.2f} seconds\n\n"
            f"Tests by Category:\n"
            f"- Equivalence Partition Tests: {len(df[~df['test_partition'].str.startswith('boundary_', na=False)])}\n"
            f"- Boundary Value Tests: {len(df[df['test_partition'].str.startswith('boundary_', na=False)])}\n\n"
            f"Language with Highest Success Rate: {success_rate.idxmax() if not success_rate.empty else 'N/A'} ({success_rate.max() if not success_rate.empty else 0:.1f}%)\n"
            f"Language with Lowest Success Rate: {success_rate.idxmin() if not success_rate.empty else 'N/A'} ({success_rate.min() if not success_rate.empty else 0:.1f}%)\n\n"
            f"Voice Gender Distribution:\n"
            f"- Male Voices: {len(df[df['voice_gender'] == 'm'])}\n"
            f"- Female Voices: {len(df[df['voice_gender'] == 'f'])}\n\n"
            f"Text Length Analysis:\n"
            f"- Min Length: {df['text_length'].min()} characters\n"
            f"- Max Length: {df['text_length'].max()} characters\n"
            f"- Avg Length: {df['text_length'].mean():.1f} characters\n\n"
            f"TensorFlow Errors: {df.get('tensorflow_error', False).sum()} tests\n\n"
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Display text summary
        plt.text(0.5, 0.5, summary_text, ha='center', va='center', fontsize=12, 
                family='monospace', transform=plt.gca().transAxes)
        plt.axis('off')
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/test_summary_{timestamp}.png", dpi=300)
        plt.close()


def run_tests():
    """Main function to run Kokoro TTS tests."""
    parser = argparse.ArgumentParser(description='Run automated tests for Kokoro TTS web app')
    parser.add_argument('--url', default='http://localhost:5000', help='URL of the Kokoro TTS web app')
    parser.add_argument('--visible', action='store_true', help='Run tests with visible browser (not headless)')
    parser.add_argument('--timeout', type=int, default=120, help='Maximum timeout for test operations in seconds')
    parser.add_argument('--output-dir', default='test_results', help='Directory to save test results and reports')
    parser.add_argument('--no-random', action='store_true', help='Do not randomize test order')
    parser.add_argument('--only-boundary', action='store_true', help='Run only boundary value tests')
    parser.add_argument('--only-partitioning', action='store_true', help='Run only equivalence partitioning tests')
    parser.add_argument('--screenshots', action='store_true', help='Take screenshots during test execution')
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    try:
        # Initialize the test automation
        tester = KokoroTTSTest(
            base_url=args.url, 
            headless=not args.visible,
            timeout=args.timeout
        )
        
        try:
            if args.only_boundary:
                print("Running only boundary value tests...")
                tester.results = tester.run_boundary_value_tests()
            elif args.only_partitioning:
                print("Running only equivalence partitioning tests...")
                tester.results = tester.run_equivalence_partition_tests(randomize=not args.no_random)
            else:
                # Run all tests
                tester.run_all_tests(randomize=not args.no_random)
            
            # Generate visualizations
            tester.visualize_results(output_dir=args.output_dir)
            
            print(f"Testing complete. Results saved to {args.output_dir}")
            
        except Exception as e:
            print(f"Error during testing: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            # Ensure cleanup
            try:
                if hasattr(tester, 'driver'):
                    tester.driver.quit()
            except:
                pass
    except Exception as e:
        print(f"Failed to initialize test environment: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_tests()