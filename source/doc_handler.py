from settings_handler import config_get
import os
import application
available_languages = os.listdir("docs")

def documentation_get():
	lang = config_get("lang")
	if not lang in available_languages:
		lang = "en"
	path = os.path.join(os.getcwd(), f"docs\\{lang}\\guide.txt")
	if not os.path.exists(path):
		return

	with open(path, "r", encoding="utf-8") as file:
		namespace = {"name": application.name, "version": application.version, "author": application.author}
		return file.read().format(**namespace)

def changelog_get():
	lang = config_get("lang")
	# Try current language
	path = os.path.join(os.getcwd(), f"docs\\{lang}\\changelog.txt")
	if os.path.exists(path):
		with open(path, "r", encoding="utf-8") as file:
			return file.read()
	
	# Try English fallback
	path = os.path.join(os.getcwd(), "docs\\en\\changelog.txt")
	if os.path.exists(path):
		with open(path, "r", encoding="utf-8") as file:
			return file.read()
			
	return None
