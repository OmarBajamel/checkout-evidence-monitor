# Base pinned from Microsoft Container Registry metadata; never built/run during implementation.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble@sha256:72bd171a9ffc2b4b59532aaa6210e21014d07093120dc25528870c0b840da1f0
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 PYTHONPATH=/opt/cem/src HOME=/tmp/cem-home
WORKDIR /opt/cem
COPY system-debs/libnss3-tools.deb /tmp/cem-nss-tools.deb
RUN echo 'e5b42390b02c21851bc04e9557ec48539a913f9b09637220c4b1db0d1386b3fb  /tmp/cem-nss-tools.deb' | sha256sum -c - && dpkg --extract /tmp/cem-nss-tools.deb /tmp/cem-nss && install -m 755 /tmp/cem-nss/usr/bin/certutil /usr/local/bin/certutil && install -m 644 /tmp/cem-nss/usr/share/doc/libnss3-tools/copyright /opt/cem/NSS-COPYRIGHT && rm -rf /tmp/cem-nss /tmp/cem-nss-tools.deb
COPY requirements-linux.lock ./requirements-linux.lock
COPY wheelhouse/ /wheelhouse/
RUN python -m pip install --no-index --find-links /wheelhouse --require-hashes --no-compile -r requirements-linux.lock && rm -rf /wheelhouse
COPY src/cem ./src/cem
COPY lab ./lab
# No CEM import, test, fixture server or browser launch in the image build.
RUN command -v certutil && command -v openssl && mkdir -p /opt/cem/lab/certs && openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj '/CN=CEM Synthetic Lab CA' -keyout /tmp/ca.key -out lab/certs/ca.crt && openssl req -newkey rsa:2048 -nodes -subj '/CN=shop.cem.test' -keyout lab/certs/fixture.key -out /tmp/fixture.csr && printf 'subjectAltName=DNS:shop.cem.test,DNS:pay.cem.test\nextendedKeyUsage=serverAuth\n' > /tmp/ext.cnf && openssl x509 -req -in /tmp/fixture.csr -CA lab/certs/ca.crt -CAkey /tmp/ca.key -CAcreateserial -days 3650 -extfile /tmp/ext.cnf -out lab/certs/fixture.crt && chmod 644 lab/certs/fixture.key && rm /tmp/ca.key /tmp/fixture.csr /tmp/ext.cnf
USER 1000:1000
ENTRYPOINT ["python", "/opt/cem/lab/entry.py"]
