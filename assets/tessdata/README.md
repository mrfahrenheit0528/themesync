# Tesseract language data

`eng.traineddata` is Tesseract's English LSTM model from
https://github.com/tesseract-ocr/tessdata_best (Apache License 2.0).

It ships with the project because the Windows install of Tesseract had no
language data, so OCR there returned nothing. `src/data_preprocessing/poster_text.py`
points Tesseract at this folder (`TESSDATA_PREFIX`) on every machine, so
Stage 0b and the content suggestions read posters the same way on the
server and on Windows (notes §3.55).
