FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# 1) Create a non-root user "jovyan" with a home directory
RUN useradd -m -s /bin/bash jovyan

# 2) Set working directory to jovyan's home
WORKDIR /home/jovyan

# 3) Copy pyproject.toml into jovyan's home with correct ownership
COPY --chown=jovyan:jovyan pyproject.toml /home/jovyan/pyproject.toml

# 4) Install dependencies via uv sync
RUN uv sync

# 5) Ensure jovyan owns everything in their home
RUN chown -R jovyan:jovyan /home/jovyan

# 6) Switch to non-root user
USER jovyan

# 7) Set HOME env for proper cache and config paths
ENV HOME=/home/jovyan

ENTRYPOINT []
CMD ["uv", "run", "jupyter", "lab", \
     "--no-browser", \
     "--ip=0.0.0.0", \
     "--NotebookApp.token=''" ]