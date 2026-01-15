run_hum:
	@echo "Corriendo monitoreo de humedad..."
	cd src/humedad_ups
	chmod +x main.py
	./main.py

run_state:
	@echo "Corriendo monitoreo de ups..."
	cd src/state_ups
	chmod +x main.py
	./main.py