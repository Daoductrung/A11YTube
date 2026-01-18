import shutil
import os
import zipfile
from paths import settings_path

def backup_data(zip_path):
	"""
	Zips the contents of settings_path to zip_path, excluding the 'updates' directory.
	"""
	with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
		for root, dirs, files in os.walk(settings_path):
			# Exclude 'updates' directory
			if 'updates' in dirs:
				dirs.remove('updates')
			
			for file in files:
				file_path = os.path.join(root, file)
				# Calculate relative path for the zip archive
				rel_path = os.path.relpath(file_path, settings_path)
				zipf.write(file_path, rel_path)
	return True

def restore_data(zip_path):
	"""
	Restores data from zip_path to settings_path, overwriting existing files.
	"""
	try:
		with zipfile.ZipFile(zip_path, 'r') as zipf:
			zipf.extractall(settings_path)
		return True
	except Exception as e:
		print(f"Restore error: {e}")
		return False
