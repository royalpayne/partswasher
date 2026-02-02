#!/bin/bash
# Upload MicroPython files to ESP32-S3
# Run this script from the parts_washer_micropython directory

PORT="/dev/ttyACM0"

echo "Uploading Parts Washer MicroPython files to ESP32-S3..."
echo "Port: $PORT"
echo ""

# Upload each file
for file in config.py stepper.py ssd1306.py main.py; do
    echo "Uploading $file..."
    mpremote connect $PORT fs cp "$file" ":$file"
    if [ $? -eq 0 ]; then
        echo "  OK"
    else
        echo "  FAILED"
        exit 1
    fi
done

echo ""
echo "All files uploaded successfully!"
echo ""
echo "To run the application:"
echo "  mpremote connect $PORT run main.py"
echo ""
echo "Or reset the ESP32-S3 to auto-start main.py"
