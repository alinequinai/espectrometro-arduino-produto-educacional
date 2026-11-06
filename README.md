# Espectrômetro Arduino – Produto Educacional

Este repositório reúne os arquivos complementares do Produto Educacional desenvolvido no âmbito da pesquisa de mestrado intitulada:

**“Nucleossíntese estelar e espectroscopia com Arduino: inovação curricular no ensino de Química no Ensino Médio paulista”.**

O material foi desenvolvido por **Aline Silva Santos Quinai**, no âmbito do Mestrado Profissional em Química em Rede Nacional – PROFQUI.

## Sobre o projeto

O Produto Educacional apresenta uma sequência didática voltada ao ensino de Química por meio da articulação entre espectroscopia, Astronomia e origem dos elementos químicos.

Entre os recursos utilizados na proposta está um espectrômetro didático construído com Arduino Uno e sensor multiespectral AS7341, associado a um aplicativo desenvolvido em Python para aquisição, tratamento e representação gráfica dos dados.

## Arquivos disponíveis

Este repositório disponibiliza:

- `espectrometro_as7341_arduino.ino` – código utilizado na programação do Arduino Uno para leitura do sensor AS7341;
- `Espectrometro_AS7341.py` – código-fonte do aplicativo desenvolvido em Python;
- `Espectrometro_AS7341.spec` – arquivo de configuração utilizado para geração do executável;
- `CRIAR_EXE.bat` – arquivo utilizado para geração do executável no Windows;
- `atom_purple.ico` – ícone utilizado no aplicativo;
- `atom_purple.png` – imagem utilizada na interface;
- `LEIA-ME.txt` – orientações complementares sobre o funcionamento e a geração do aplicativo;
- arquivo `.3mf` – modelo tridimensional da caixa utilizada para acondicionamento do Arduino Uno, da protoboard e do sensor AS7341.

## Aplicativo para Windows

A versão executável do aplicativo está disponível na seção **Releases** deste repositório.

Arquivo principal:

`Espectrometro_AS7341.exe`

O aplicativo permite:

- leitura dos oito canais espectrais do sensor AS7341;
- correção do sinal de escuro;
- normalização dos dados;
- visualização das respostas espectrais em gráficos;
- identificação do canal de maior resposta;
- exportação dos dados para arquivo CSV;
- salvamento das representações gráficas.

## Sensor AS7341

O aplicativo considera oito canais espectrais na região visível, com comprimentos de onda centrais aproximados em:

**415, 445, 480, 515, 555, 590, 630 e 680 nm.**

Os valores registrados pelo sensor correspondem a contagens digitais proporcionais à luz incidente e não devem ser interpretados como medidas absolutas de intensidade radiométrica.

## Uso do aplicativo

Antes da realização das medições, recomenda-se executar a correção do sinal de escuro com o sensor completamente coberto.

O aplicativo utiliza 20 leituras válidas para determinar o valor médio do sinal de escuro de cada canal. Esses valores são posteriormente subtraídos das novas leituras.

Após esse procedimento, o sistema pode apresentar os valores brutos e normalizados dos canais espectrais.

A normalização permite destacar a distribuição relativa da resposta entre os canais, reduzindo a influência de variações globais de intensidade relacionadas, por exemplo, à distância e ao posicionamento da fonte luminosa.

## Arquivo para impressão 3D

O modelo tridimensional da estrutura utilizada para acondicionar o conjunto experimental está disponível em formato **3MF**.

A estrutura foi projetada para acomodar o Arduino Uno, a protoboard e o sensor AS7341 e possui abertura destinada à entrada da luz proveniente da fonte analisada.

## DOI

Uma versão arquivada deste repositório encontra-se disponível no Zenodo.

**DOI:** https://doi.org/10.5281/zenodo.24017146

## Autoria

**Aline Silva Santos Quinai**

Mestrado Profissional em Química em Rede Nacional – PROFQUI

2026
