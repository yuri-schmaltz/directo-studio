# Original User Request

## 2026-07-26T23:21:59Z

<USER_REQUEST>
Arquitetar e implementar um subsistema/módulo completo no Directo Studio para orquestração de geração local de mídias (vídeos, overlays, TTS/vozes, BGM, SFX, legendas via Whisper) e gerenciamento de Bíblia de Estilo (consistência de personagens, ambientes, LoRAs, seeds e prompts mestre).

Working directory: /home/yuri/Documentos/directo
Integrity mode: development

## Requirements

### R1. Subsistema de Bíblia de Estilo & Consistência (Style Bible Engine)
Implementar a estrutura de dados e gerenciador para "Bíblias de Estilo", permitindo definir:
- **Personagens**: Prompts base, visual anchors, LoRAs associados, seeds fixas/variação, exemplos de referência.
- **Ambientes**: Prompts de cenários, iluminação, paletas de cores, style tokens.
- **Diretrizes de Estilo**: Parâmetros globais de imagem/vídeo, proporção de tela, filtros de áudio/voz.

### R2. Orquestrador de Geração Local de Mídias (Local Media Generation Hub)
Desenvolver adaptadores e pipeline assíncrono para os seguintes engines e fluxos locais:
- **Vídeo & Overlays**: Driver de comunicação com ComfyUI/AnimateDiff/FFmpeg para renderização de cenas e adição de overlays visuais.
- **Vozes & Legendas**: Integração com motores locais de TTS (Piper/Bark/Coqui) para síntese de voz por personagem e alinhamento/geração de legendas (.srt/.vtt/.json) via Whisper.
- **Áudio & Trilhas**: Gerenciador de BGM e SFX locais com mixagem dinâmica de volume e sidechain ducking.

### R3. API Endpoints e Hooks para a UI do Directo Studio
Expor endpoints REST/WebSockets no backend FastAPI (`directo/`) e integrar os tipos e schemas necessários para consumo no frontend `ui/`, permitindo selecionar e disparar pipelines de geração com a Bíblia de Estilo ativa.

## Verification Plan & Resources

### Programmatic Verification
- **Testes Unitários e de Integração (pytest)**:
  - Validar serialização/deserialização e persistência de Bíblias de Estilo (`tests/test_style_bible.py`).
  - Validar a composição de prompts e injeção de LoRAs/seeds baseados nos personagens da Bíblia de Estilo (`tests/test_prompt_builder.py`).
  - Testar o orquestrador de áudio (mixagem, ducking, formatação de legendas Whisper) com mocks de engines locais (`tests/test_local_media_orchestrator.py`).
  - Testar os endpoints FastAPI de geração e consulta de status (`tests/test_local_gen_api.py`).

## Acceptance Criteria

### Bíblia de Estilo
- [ ] O sistema permite criar, carregar, atualizar e exportar/importar arquivos de Bíblia de Estilo em formato JSON/YAML.
- [ ] O construtor de prompts injeta automaticamente as características de personagens e cenários definidos na Bíblia de Estilo durante o fluxo de geração.

### Orquestrador de Mídias
- [ ] O pipeline de voz gera arquivos de áudio por fala e sincroniza legendas com timestamps exatos.
- [ ] O pipeline de mixagem de áudio combina voz, BGM e SFX aplicando regras de ducking sem distorção.
- [ ] O adaptador de vídeo constrói e envia workflows válidos para execução em endpoints de geração local (ex: ComfyUI API) com fallbacks graciosos caso o serviço local esteja offline.

### API & Qualidade de Código
- [ ] Todos os novos módulos passam em `pytest` sem regressões nos testes existentes.
- [ ] O código segue a estrutura arquitetural modular já estabelecida em `directo/`.
</USER_REQUEST>
