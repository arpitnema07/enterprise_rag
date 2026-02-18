dnf -y install dnf-plugins-core

dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo

dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker
systemctl status docker

docker version

mkdir -p /store/Arpit/{redis,qdrant,ollama}
chmod -R 755 /store/Arpit
