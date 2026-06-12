-- Tabela de relatórios técnicos
CREATE TABLE relatorios (
  id               UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  criado_em        TIMESTAMPTZ DEFAULT NOW(),
  tecnico          TEXT        NOT NULL,
  situacao_encontrada  TEXT,
  resolucao_problema   TEXT,
  equipamento_status   TEXT,
  equipamento_obs      TEXT,
  maior_sinal          TEXT,
  materiais_utilizados TEXT,
  materiais_recolhidos TEXT,
  obs_fotos            TEXT,
  check_sinal_fibra    BOOLEAN DEFAULT FALSE,
  check_serial         BOOLEAN DEFAULT FALSE,
  check_cto            BOOLEAN DEFAULT FALSE,
  check_panoramica     BOOLEAN DEFAULT FALSE,
  check_sobra          BOOLEAN DEFAULT FALSE,
  check_metragem       BOOLEAN DEFAULT FALSE,
  check_velocidade     BOOLEAN DEFAULT FALSE,
  check_local_ont      BOOLEAN DEFAULT FALSE,
  check_frente         BOOLEAN DEFAULT FALSE,
  relatorio_completo   TEXT
);

-- Desabilita RLS para acesso via chave do servidor
ALTER TABLE relatorios DISABLE ROW LEVEL SECURITY;

-- Índices para filtros comuns
CREATE INDEX idx_relatorios_tecnico   ON relatorios (tecnico);
CREATE INDEX idx_relatorios_criado_em ON relatorios (criado_em DESC);
