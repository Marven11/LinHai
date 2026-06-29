{
  description = "Python venv development template";

  inputs = {
    utils.url = "github:numtide/flake-utils";
    nur = {
      url = "github:nix-community/NUR";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    etherGhost = {
      url = "github:Marven11/EtherGhost";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      utils,
      nur,
      etherGhost,
      ...
    }:
    utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;

          overlays = [ nur.overlays.default ];
        };

        python-telegram-bot' = pkgs.python3Packages.buildPythonPackage rec {
          pname = "python-telegram-bot";
          version = "22.7";
          pyproject = true;

          src = pkgs.fetchFromGitHub {
            owner = "python-telegram-bot";
            repo = "python-telegram-bot";
            tag = "v${version}";
            hash = "sha256-+mbVN1XFChUMYReHMjQd1tx5gYpP1CWGNtuZCoY9TMo=";
          };

          build-system = [
            pkgs.python3Packages.setuptools
            pkgs.python3Packages.hatchling
          ];

          dependencies = [ pkgs.python3Packages.httpx ];
        };

        quickjs-ng' = pkgs.python3Packages.buildPythonPackage rec {
          pname = "python-quickjs-ng";
          version = "0.12.1.1";
          pyproject = true;

          src = pkgs.fetchgit {
            url = "http://192.168.114.149:3000/Marven11/quickjs-ng.git";
            rev = "v${version}";
            fetchSubmodules = true;
            hash = "sha256-PdPQRnU+v+wdzhSL3JBuuEW8ihEMnKZJYzPQs5cHyS8=";
          };

          build-system = [
            pkgs.python3Packages.setuptools
          ];

          pythonImportsCheck = [ "quickjs" ];
        };
      in
      let
        pythonDeps =
          with pkgs.python3Packages;
          [
            etherGhost.packages.${system}.default
            openai
            anthropic
            httpx
            beautifulsoup4
            mistune
            textual
            mcp
            pyte
            pydantic
            chardet
            bashlex
            pillow
            tomli-w
            croniter
            pathspec
            websockets
            pyyaml
            jsonschema
            python-telegram-bot'
            quickjs-ng'
          ];
      in
      {
        packages.default =
          with pkgs.python3Packages;
          buildPythonPackage rec {
            pname = "linhai";
            doCheck = false;
            pythonRemoveDeps = [ "python-quickjs-ng" ];
            pyproject = true;

            nativeBuildInputs = [ pkgs.installShellFiles ];
            buildInputs = [ pkgs.tmux ];

            build-system = [
              hatchling
            ];

            dependencies = pythonDeps;

            src = ./.;
            version = "0.5.1-dev-${self.shortRev or self.dirtyShortRev or "dirty"}";
          };

        devShells.default = pkgs.mkShell {
          packages =
            with pkgs;
            [
              (python3.withPackages (
                ps: pythonDeps ++ (with ps; [ pylint black ])
              ))
              pyright
              uv
              tmux
            ];
        };
      }
    );
}
