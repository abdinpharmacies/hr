def post_init_hook(env):
    env.cr.execute(
        """
        UPDATE ab_product
           SET website_sale_available = TRUE
         WHERE active IS TRUE
           AND allow_sale IS TRUE
        """
    )
