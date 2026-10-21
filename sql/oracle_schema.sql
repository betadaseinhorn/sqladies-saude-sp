-- =============================================================================
-- SQLadies · adaptação demonstrativa do projeto entregue à Oracle
-- Modelo relacional (DDL Oracle) equivalente ao banco SQLite usado pela demo.
-- Fonte 1 (estruturada): SIH/SUS · Fonte 2 (semiestruturada, JSON): CNES via API
-- =============================================================================

-- ---------------------------------------------------------------- dimensões --
CREATE TABLE dim_municipio (
    cod_mun       NUMBER(6)      PRIMARY KEY,          -- código IBGE (6 dígitos)
    nome          VARCHAR2(80)   NOT NULL,
    drs_num       NUMBER(2),                            -- Departamento Regional de Saúde (1..17)
    drs_nome      VARCHAR2(80),
    regsaud_cod   VARCHAR2(5),                          -- Região de Saúde (CIR)
    regsaud_nome  VARCHAR2(80),
    rras_cod      VARCHAR2(4),                          -- Rede Regional de Atenção à Saúde
    rras_nome     VARCHAR2(20),
    lat           NUMBER(10, 6),
    lon           NUMBER(10, 6),
    area_km2      NUMBER(10, 3),
    capital       NUMBER(1)      DEFAULT 0,
    pop_2024      NUMBER(9),
    pop_2025      NUMBER(9)
);

CREATE TABLE dim_cid_capitulo (
    cap_cod   VARCHAR2(5)   PRIMARY KEY,                -- I..XXII
    cap_num   NUMBER(2)     NOT NULL,
    inicio    VARCHAR2(3),
    fim       VARCHAR2(3),
    cap_nome  VARCHAR2(60)
);

-- Cadastro CNES vindo da API em JSON: colunas fixas + atributos variáveis em JSON
CREATE TABLE dim_estabelecimento (
    cnes               NUMBER(7)     PRIMARY KEY,
    nome               VARCHAR2(200),
    razao_social       VARCHAR2(200),
    tipo_cod           NUMBER(3),
    tipo_desc          VARCHAR2(80),
    grupo              VARCHAR2(20),                    -- Hospital | UBS | Urgência
    cod_mun            NUMBER(6)     REFERENCES dim_municipio (cod_mun),
    gestao             VARCHAR2(2),
    esfera             VARCHAR2(30),
    natureza_juridica  VARCHAR2(10),
    telefone           VARCHAR2(40),
    email              VARCHAR2(120),
    cep                VARCHAR2(8),
    endereco           VARCHAR2(200),
    numero             VARCHAR2(20),
    bairro             VARCHAR2(100),
    lat                NUMBER(10, 6),
    lon                NUMBER(10, 6),
    atende_sus_amb     VARCHAR2(3),
    centro_cirurgico   NUMBER(1),
    centro_obstetrico  NUMBER(1),
    centro_neonatal    NUMBER(1),
    atend_hospitalar   NUMBER(1),
    data_atualizacao   DATE,
    atributos_json     CLOB          CONSTRAINT ck_est_json CHECK (atributos_json IS JSON)
);

-- Registro JSON original de cada estabelecimento, sem transformação
CREATE TABLE cnes_raw (
    cnes      NUMBER(7)  PRIMARY KEY,
    tipo_cod  NUMBER(3),
    json      CLOB       CONSTRAINT ck_raw_json CHECK (json IS JSON)
);

-- -------------------------------------------------------------------- fatos --
-- Uma linha por AIH (SIH/SUS RD-SP)
CREATE TABLE fato_internacao (
    competencia       NUMBER(6),                        -- AAAAMM de processamento
    n_aih             VARCHAR2(13),
    ident             NUMBER(1),                        -- 1 = normal, 5 = longa permanência
    conta_internacao  NUMBER(1),                        -- 1 = conta como internação
    cnes              NUMBER(7),
    mun_res           NUMBER(6),                        -- município de residência
    mun_int           NUMBER(6),                        -- município de internação
    sexo              VARCHAR2(1),
    idade             NUMBER(5, 1),
    faixa_etaria      VARCHAR2(6),
    diag_princ        VARCHAR2(4),
    cap_cid           VARCHAR2(5)   REFERENCES dim_cid_capitulo (cap_cod),
    carater           VARCHAR2(10),                     -- Eletivo | Urgência
    dt_inter          DATE,
    mes_inter         VARCHAR2(7),                      -- AAAA-MM da internação
    dt_saida          DATE,
    dias_perm         NUMBER(5),
    uti_dias          NUMBER(5),
    valor_total       NUMBER(12, 2),
    valor_uti         NUMBER(12, 2),
    morte             NUMBER(1),
    proc_rea          VARCHAR2(10),
    espec             VARCHAR2(2)
)
PARTITION BY RANGE (dt_inter) INTERVAL (NUMTOYMINTERVAL(1, 'MONTH'))
    (PARTITION p_inicial VALUES LESS THAN (DATE '2024-01-01'));

CREATE INDEX ix_fi_mes     ON fato_internacao (mes_inter)  LOCAL;
CREATE INDEX ix_fi_mun_int ON fato_internacao (mun_int)    LOCAL;
CREATE INDEX ix_fi_mun_res ON fato_internacao (mun_res)    LOCAL;
CREATE INDEX ix_fi_cnes    ON fato_internacao (cnes)       LOCAL;

-- Leitos por estabelecimento e competência (CNES-LT)
CREATE TABLE fato_leitos (
    competencia       NUMBER(6),
    cnes              NUMBER(7),
    cod_mun           NUMBER(6),
    tipo_unidade_cod  NUMBER(3),
    tp_leito          VARCHAR2(40),
    cod_leito         VARCHAR2(2),
    qt_exist          NUMBER(5),
    qt_sus            NUMBER(5)
);
CREATE INDEX ix_lt_cnes ON fato_leitos (cnes, competencia);
CREATE INDEX ix_lt_mun  ON fato_leitos (cod_mun);

-- ----------------------------------------------------------------- agregados --
-- Mês × hospital × capítulo CID × caráter (base dos dashboards por hospital/região)
CREATE MATERIALIZED VIEW agg_mensal_hosp
BUILD IMMEDIATE REFRESH COMPLETE ON DEMAND AS
SELECT mes_inter, cnes, mun_int, cap_cid, carater,
       SUM(conta_internacao)                                          AS internacoes,
       COUNT(*)                                                       AS aihs,
       SUM(dias_perm * conta_internacao)                              AS dias_perm,
       SUM(valor_total)                                               AS valor_total,
       SUM(morte * conta_internacao)                                  AS obitos,
       SUM(uti_dias)                                                  AS uti_dias,
       SUM(CASE WHEN idade >= 60 THEN conta_internacao ELSE 0 END)    AS idosos,
       SUM(CASE WHEN mun_res <> mun_int THEN conta_internacao ELSE 0 END) AS residentes_fora
FROM fato_internacao
GROUP BY mes_inter, cnes, mun_int, cap_cid, carater;

-- Mês × município de residência × capítulo CID × caráter × faixa etária (demanda da população)
CREATE MATERIALIZED VIEW agg_mensal_res
BUILD IMMEDIATE REFRESH COMPLETE ON DEMAND AS
SELECT mes_inter, mun_res, cap_cid, carater, faixa_etaria,
       SUM(conta_internacao)                                          AS internacoes,
       SUM(dias_perm * conta_internacao)                              AS dias_perm,
       SUM(valor_total)                                               AS valor_total,
       SUM(morte * conta_internacao)                                  AS obitos,
       SUM(CASE WHEN mun_res <> mun_int THEN conta_internacao ELSE 0 END) AS internadas_fora
FROM fato_internacao
WHERE mun_res BETWEEN 350000 AND 359999
GROUP BY mes_inter, mun_res, cap_cid, carater, faixa_etaria;

-- As tabelas res_* (res_municipio, res_hospital, res_cluster_*, res_fatores, ...)
-- são geradas pelo pipeline de análise em Python (analysis/run_all.py).
