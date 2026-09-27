# Product Image Synchronization

The image synchronization flow keeps the Odoo website product image in
`product.template.image_1920`.

## Configuration

The image root is read from the system parameter:

```text
ab_website_sale_product.image_directory
```

Default value:

```text
/opt/odoo19/product_images
```

## Supported Layouts

```text
/opt/odoo19/product_images/12345.jpg
/opt/odoo19/product_images/12345/main.jpg
/opt/odoo19/product_images/products/12345/main.webp
/opt/odoo19/product_images/anything/12345/01.png
```

Supported extensions are `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, and `.bmp`.
Extensions are matched case-insensitively.

## Flow

```text
Configured Image Root
        ↓
Recursive Scanner
        ↓
Image Index
        ↓
Deterministic Matcher
        ↓
Dry-Run / Sync Plan
        ↓
Batch Synchronization
        ↓
product.template.image_1920
```

## Matching Priority

The matcher uses exact identifiers only:

```text
product code
→ barcode
→ Eplus serial / external identifier
```

For each identifier, both filename stems and parent folder names are considered.

## Main Image Convention

If multiple images match one product, the primary image is selected only when
there is a deterministic convention:

```text
main.jpg
main.jpeg
main.png
main.webp
```

Then numbered images such as:

```text
01.jpg
02.jpg
03.jpg
```

If multiple candidates have the same priority, the product is reported as
`ambiguous` and no image is written.

## Safety Behavior

- Missing source image: keep the existing Odoo image.
- Ambiguous match: do not write an image.
- Corrupt image: report `invalid` and continue.
- Unchanged checksum: skip the write.
- Placeholder image: treat the module placeholder as no real product image, so
  adding the first real image does not trigger replacement confirmation.

## Admin Workflow

Use the existing `Sync Images` button on Abdin products.

1. Set or confirm the image root directory.
2. Run `Scan / Preview`.
3. Review the summary and report lines.
4. Run `Synchronize Images` to update `product.template.image_1920`.
5. If matched products already have different images, review the displayed count
   and choose whether to replace those images or keep them. New images can still
   be synchronized without replacing existing ones.
