SQL_DELIVERY_POINTS = """
select 
    s.sto_code as store_code
    ,e.e_code as employee_code
    ,case 
        when convert(date, d.sec_insert_date)<%(start_date)s and convert(date,d.sec_update_date) between %(start_date)s and %(end_date)s 
            then 1
        else 0 end as order_returned
    ,count(h.sth_id) orders_count
    ,sum (case 
        when convert(date, d.sec_insert_date)<%(start_date)s and convert(date,d.sec_update_date) between %(start_date)s and %(end_date)s 
            then (d.itm_back * d.itm_sell)*-1
        when convert(date, h.sec_insert_date) between %(start_date)s and  %(end_date)s
            then (d.qnty-d.itm_back)*d.itm_sell
        end) as total_points
    ,min(convert(date, isnull(d.sec_update_date,d.sec_insert_date))) as start_date,
    max(convert(date, isnull(d.sec_update_date,d.sec_insert_date))) as end_date
from r_sales_trans_d d
join r_sales_trans_h h on h.sth_id=d.sth_id and h.sto_id=d.std_stock_id
join store s on s.sto_id=h.sto_id
left join r_sales_deliv_info rd on rd.sth_id=h.sth_id and rd.sdi_sto_id=h.sto_id
left join Employee e on e.e_id=rd.deliv_emp_id
where 
    itm_id=73030
    and case 
        when convert(date, d.sec_insert_date)<%(start_date)s and convert(date,d.sec_update_date) between %(start_date)s and %(end_date)s 
            then (d.itm_back * d.itm_sell)*-1
        when convert(date, h.sec_insert_date) between %(start_date)s and  %(end_date)s
            then (d.qnty-d.itm_back)*d.itm_sell
        end != 0
    and d.sec_insert_date>='2023-04-01' and d.sec_update_date>='2023-04-01'
group by s.sto_code,e.e_code,
    case 
        when convert(date, d.sec_insert_date)<%(start_date)s and convert(date,d.sec_update_date) between %(start_date)s and %(end_date)s 
            then 1
        else 0
    end
order by e.e_code
"""
