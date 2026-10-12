-- Przy zmianie czasu doba ma 23 albo 25 godzin, poza tym 24. Inna liczba = blad stref czasowych.
-- Pomijamy pierwsza i ostatnia dobe zakresu, bo moga byc uciete.
with doby as (
    select data, count(*) as godzin from {{ ref('dim_czas') }} group by data
)
select * from doby
where godzin not in (23, 24, 25)
  and data > (select min(data) from doby) and data < (select max(data) from doby)
