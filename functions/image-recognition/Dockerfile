FROM --platform=${TARGETPLATFORM:-linux/amd64} ghcr.io/openfaas/classic-watchdog:0.2.1 as watchdog
FROM --platform=${TARGETPLATFORM:-linux/amd64} graphcore/pytorch

ARG TARGETPLATFORM
ARG BUILDPLATFORM

COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
RUN chmod +x /usr/bin/fwatchdog && mkdir /home/app/

WORKDIR /home/app/

COPY __init__.py handler.py index.py imagenet_class_index.json ./
COPY images/ ./images/
COPY model/ ./model/

ENV fprocess="python3 index.py 2> /dev/null"
EXPOSE 8080

HEALTHCHECK --interval=3s CMD [ -e /tmp/.lock ] || exit 1

CMD ["fwatchdog"]
