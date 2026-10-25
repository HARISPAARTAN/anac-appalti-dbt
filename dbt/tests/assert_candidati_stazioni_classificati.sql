-- Errore: una stazione candidata (vedi int_stazioni_da_verificare) non è in nessuno dei due seed. Va letta e
-- classificata: persona fisica in ausa_persone_fisiche, ente in ausa_enti_verificati (solo codici AUSA, mai nomi).
-- Nel dubbio, persona. La tabella di audit di questo test mostra il nome, solo in locale.
select c.codice_ausa, c.codice_fiscale, c.denominazione
from {{ ref('int_stazioni_da_verificare') }} as c
where c.codice_ausa not in (select upper(trim(codice_ausa)) from {{ ref('ausa_enti_verificati') }})
    and c.codice_ausa not in (select upper(trim(codice_ausa)) from {{ ref('ausa_persone_fisiche') }})
