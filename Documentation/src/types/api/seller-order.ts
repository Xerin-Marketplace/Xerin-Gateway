export type SellerOrderStatus = "new"|"accepted"|"processing"|"ready_to_ship"|"shipped"|"delivered"|"cancellation_requested"|"cancelled";
export type SellerOrderItem={id:string;product_id:string;variant_id?:string|null;product_name:string;variant_name?:string|null;quantity:number;unit_price:number|string;total_price:number|string};
export type SellerOrder={id:string;order_id:string;seller_id:string;order_status:string;seller_status:SellerOrderStatus;currency:string;seller_subtotal:number|string;item_count:number;customer_name:string;customer_phone?:string|null;shipping_address?:Record<string,unknown>|null;shipping_method_name?:string|null;shipping_carrier?:string|null;estimated_delivery_from?:string|null;estimated_delivery_to?:string|null;seller_notes?:string|null;cancellation_reason?:string|null;items:SellerOrderItem[];shipment?:Record<string,unknown>|null;created_at:string;updated_at?:string|null};
export type SellerOrderList={total:number;page:number;page_size:number;results:SellerOrder[]};
export type SellerOrderSummary={total_orders:number;new_orders:number;accepted_orders:number;processing_orders:number;ready_to_ship_orders:number;shipped_orders:number;delivered_orders:number;cancellation_requests:number;gross_sales:number|string;units_sold:number};
export type SellerOrderQuery={page?:number;page_size?:number;search?:string;status?:SellerOrderStatus;date_from?:string;date_to?:string};


export type SellerOrderMessageAttachment = {
  id: string;
  file_url: string;
  file_name?: string | null;
  mime_type?: string | null;
  created_at: string;
};

export type SellerOrderMessage = {
  id: string;
  seller_order_id: string;
  sender_user_id?: string | null;
  sender_role_label?: string | null;
  message: string;
  is_internal: boolean;
  attachments: SellerOrderMessageAttachment[];
  created_at: string;
};

export type SellerOrderMessageCreate = {
  message: string;
  is_internal?: boolean;
  attachment_urls?: string[];
};


export type SellerOrderPackageAttachment = {
  id: string;
  file_url: string;
  file_name?: string | null;
  mime_type?: string | null;
  created_at: string;
};

export type SellerOrderPackage = {
  id: string;
  seller_order_id: string;
  weight_kg?: number | string | null;
  length_cm?: number | string | null;
  width_cm?: number | string | null;
  height_cm?: number | string | null;
  package_count: number;
  notes?: string | null;
  is_ready: boolean;
  prepared_at?: string | null;
  attachments: SellerOrderPackageAttachment[];
  created_at: string;
  updated_at?: string | null;
};

export type SellerOrderPackageUpsert = {
  weight_kg?: number | null;
  length_cm?: number | null;
  width_cm?: number | null;
  height_cm?: number | null;
  package_count: number;
  notes?: string | null;
  is_ready: boolean;
  attachment_urls?: string[];
};
