FROM python
COPY tba.py tba.mjs requirements.txt ./
RUN pip install -r requirements.txt
EXPOSE 5000
VOLUME /config
ENV TBA_CONFIG_PATH=/config/tba.ini
ENTRYPOINT ["python","tba.py"]