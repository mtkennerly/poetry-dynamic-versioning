Vagrant.configure('2') do |config|
  config.vm.provider 'virtualbox' do |vb|
    vb.memory = '2048'
    vb.cpus = 2
  end

  config.vm.box = 'ubuntu/bionic64'
  config.vm.provision 'shell', privileged: false, inline: <<~SHELL
    echo 'PATH=$PATH:~/.local/bin' >> ~/.bashrc
    echo 'export PATH="/home/vagrant/.pyenv/bin:$PATH"' >> ~/.bashrc
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc
    echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc

    curl -L https://raw.githubusercontent.com/yyuu/pyenv-installer/master/bin/pyenv-installer | bash

    sudo apt-get update
    sudo apt-get install -y --no-install-recommends \
      make \
      build-essential \
      libssl-dev \
      zlib1g-dev \
      libbz2-dev \
      libreadline-dev \
      libsqlite3-dev \
      wget \
      curl \
      llvm \
      libncurses5-dev \
      xz-utils \
      tk-dev \
      libxml2-dev \
      libxmlsec1-dev \
      libffi-dev \
      liblzma-dev
  SHELL
end
