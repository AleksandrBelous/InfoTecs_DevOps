# -*- mode: ruby -*-
# vi: set ft=ruby :

# All Vagrant configuration is done below. The "2" in Vagrant.configure
# configures the configuration version (we support older styles for
# backwards compatibility). Please don't change it unless you know what
# you're doing.

Vagrant.configure("2") do |config|
    # The most common configuration options are documented and commented below.
    # For a complete reference, please see the online documentation at
    # https://docs.vagrantup.com.

    # полностью отключить vbguest
    config.vbguest.auto_update = false   # не проверять версии
    config.vbguest.no_install  = true    # и вовсе не пытаться устанавливать

    # Завернём нашу машину в Vagrant-идентификатор bookworm и далее будем уже работать с ВМ bookworm, а не с default
    config.vm.define "bookworm" do |bookworm|

        # Every Vagrant development environment requires a box. You can search for
        # boxes at https://vagrantcloud.com/search.
        bookworm.vm.box = "debian/bookworm64"

        bookworm.vm.hostname = "bookworm"

        # Disable automatic box update checking. If you disable this, then
        # boxes will only be checked for updates when the user runs
        # `vagrant box outdated`. This is not recommended.
        # bookworm.vm.box_check_update = false

        # Create a forwarded port mapping which allows access to a specific port
        # within the machine from a port on the host machine. In the example below,
        # accessing "localhost:8080" will access port 80 on the guest machine.
        # NOTE: This will enable public access to the opened port
        # config.vm.network "forwarded_port", guest: 80, host: 8080

        # Create a forwarded port mapping which allows access to a specific port
        # within the machine from a port on the host machine and only allow access
        # via 127.0.0.1 to disable public access
        # config.vm.network "forwarded_port", guest: 80, host: 8080, host_ip: "127.0.0.1"

        # Create a private network, which allows host-only access to the machine
        # using a specific IP.
        bookworm.vm.network "private_network", ip: "192.168.56.10"

        # Create a public network, which generally matched to bridged network.
        # Bridged networks make the machine appear as another physical device on
        # your network.
        # config.vm.network "public_network"

        # Share an additional folder to the guest VM. The first argument is
        # the path on the host to the actual folder. The second argument is
        # the path on the guest to mount the folder. And the optional third
        # argument is a set of non-required options.
        # config.vm.synced_folder "../data", "/vagrant_data"
        bookworm.vm.synced_folder "./sqlite-amalgamation-3260000/", "/home/vagrant/sqlite-amalgamation-3260000/",
            type: "rsync",
            rsync__exclude: ["Release", "build", "logs_lin", "logs_win", "*.c", "*.h"]

        # Disable the default share of the current code directory. Doing this
        # provides improved isolation between the vagrant box and your host
        # by making sure your Vagrantfile isn't accessible to the vagrant box.
        # If you use this you may want to enable additional shared subfolders as
        # shown above.
        # config.vm.synced_folder ".", "/vagrant", disabled: true

        # Provider-specific configuration so you can fine-tune various
        # backing providers for Vagrant. These expose provider-specific options.
        # Example for VirtualBox:
        #
        bookworm.vm.provider "virtualbox" do |vb|
            # Display the VirtualBox GUI when booting the machine
            # vb.gui = true

            # Customize the amount of memory on the VM:
            vb.memory = "2048"
            vb.cpus = 4
        end
        #
        # View the documentation for the provider you are using for more
        # information on available options.

        # Enable provisioning with a shell script. Additional provisioners such as
        # Ansible, Chef, Docker, Puppet and Salt are also available. Please see the
        # documentation for more information about their specific syntax and use.
        # config.vm.provision "shell", inline: <<-SHELL
        #   apt-get update
        #   apt-get install -y apache2
        # SHELL

        bookworm.vm.provision "ansible" do |ansible|
            ansible.playbook = "ansible/playbooks/docker_install.yml"
            ansible.inventory_path = "ansible/inventory.ini"
            ansible.limit = "bookworm" # запускаем плейбук только на хосте bookworm
        end

        bookworm.vm.provision "ansible" do |ansible|
            ansible.playbook = "ansible/playbooks/sqlite_build.yml"
            ansible.inventory_path = "ansible/inventory.ini"
            ansible.limit = "bookworm"
        end
    end
end
