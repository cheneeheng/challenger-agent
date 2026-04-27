terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
      # ACM certificates for CloudFront must be in us-east-1.
      # The root module passes aws.us_east_1 via providers = { aws.us_east_1 = ... }
      configuration_aliases = [aws.us_east_1]
    }
  }
}

# ---- ACM certificate (must be in us-east-1) --------------------------------

resource "aws_acm_certificate" "frontend" {
  provider = aws.us_east_1

  domain_name               = var.domain_name
  subject_alternative_names = ["*.${var.domain_name}"]
  validation_method         = "DNS"

  tags = { Name = var.app_name }

  lifecycle {
    create_before_destroy = true
  }
}

# DNS validation records — add these to your DNS provider before apply
output "acm_validation_records" {
  value = {
    for dvo in aws_acm_certificate.frontend.domain_validation_options : dvo.domain_name => {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  }
  description = "Add these CNAME records to your DNS provider to validate the ACM certificate"
}

# ---- CloudFront OAC --------------------------------------------------------

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.app_name}-oac"
  description                       = "S3 origin for ${var.app_name} frontend"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ---- Cache policies --------------------------------------------------------

resource "aws_cloudfront_cache_policy" "immutable_assets" {
  name        = "${var.app_name}-immutable-assets"
  comment     = "Vite hashed assets — 1 year TTL"
  min_ttl     = 31536000
  default_ttl = 31536000
  max_ttl     = 31536000

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config { cookie_behavior = "none" }
    headers_config { header_behavior = "none" }
    query_strings_config { query_string_behavior = "none" }
    enable_accept_encoding_gzip   = true
    enable_accept_encoding_brotli = true
  }
}

resource "aws_cloudfront_cache_policy" "no_cache" {
  name        = "${var.app_name}-no-cache"
  comment     = "index.html — always revalidate"
  min_ttl     = 0
  default_ttl = 0
  max_ttl     = 1

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config { cookie_behavior = "none" }
    headers_config { header_behavior = "none" }
    query_strings_config { query_string_behavior = "none" }
  }
}

# ---- Distribution ----------------------------------------------------------

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  aliases             = [var.domain_name]
  price_class         = "PriceClass_100"

  origin {
    domain_name              = var.s3_regional_domain
    origin_id                = "s3-frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # Vite assets have content-hashed filenames — cache forever
  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-frontend"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    cache_policy_id        = aws_cloudfront_cache_policy.immutable_assets.id
  }

  # index.html must never be cached so SPA deploys take effect immediately
  ordered_cache_behavior {
    path_pattern           = "/index.html"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-frontend"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    cache_policy_id        = aws_cloudfront_cache_policy.no_cache.id
  }

  # SPA routing: unknown paths return index.html so the client-side router handles them
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.frontend.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = { Name = "${var.app_name}-frontend" }
}
