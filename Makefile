instalacion_requisitos:
	@echo "Instalando python3";\
	sudo apt install python3 -y;\

	@echo "Instalando pip";\
	sudo apt install python3-pip -y;\
	sudo apt install python3-venv -y;\

	@echo "Instalando easysnmp y snmp";\
	sudo apt install snmp -y;\
	sudo apt install build-essential libsnmp-dev -y;\
	sudo apt install python3-easysnmp;\

	@echo "Instalando dotenv";\
	sudo apt install python3-dotenv;

	@echo "Instalando httplib2";\
	sudo apt install python3-httplib2;\

	@echo "Instalando pytest" ;\
	sudo apt install python3-pytest;\
	sudo apt install python3-pytest-cov

run_hum:
	@echo "Corriendo monitoreo de humedad..."
	cd src/;\
	chmod +x main.py;\
	./main.py

run_state:
	@echo "Corriendo monitoreo de ups..."
	cd ./src/;\
	chmod +x main.py;\
	./main.py

install_dependencias_ci:
	python3 -m venv venv
	venv/bin/python -m pip install pytest python-dotenv httplib2 easysnmp
