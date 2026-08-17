import axiosInstance from "../client";
import type {
  SellerOrder,
  SellerOrderList,
  SellerOrderQuery,
  SellerOrderSummary,
  SellerOrderMessage,
  SellerOrderMessageCreate,
  SellerOrderPackage,
  SellerOrderPackageUpsert,
} from "@/types/api/seller-order";
const ROOT="/seller/orders";
export const sellerOrdersApi={
 summary:async()=>(await axiosInstance.get<SellerOrderSummary>(`${ROOT}/summary`)).data,
 list:async(params:SellerOrderQuery={})=>(await axiosInstance.get<SellerOrderList>(ROOT,{params})).data,
 get:async(id:string)=>(await axiosInstance.get<SellerOrder>(`${ROOT}/${id}`)).data,
 accept:async(id:string,notes?:string)=>(await axiosInstance.post<SellerOrder>(`${ROOT}/${id}/accept`,{notes:notes||null})).data,
 process:async(id:string,notes?:string)=>(await axiosInstance.post<SellerOrder>(`${ROOT}/${id}/start-processing`,{notes:notes||null})).data,
 ready:async(id:string,notes?:string)=>(await axiosInstance.post<SellerOrder>(`${ROOT}/${id}/ready-to-ship`,{notes:notes||null})).data,
 dispatch:async(id:string,payload:{carrier_name:string;tracking_number:string;tracking_url?:string|null;location?:string|null;notes?:string|null})=>(await axiosInstance.post<SellerOrder>(`${ROOT}/${id}/dispatch`,payload)).data,
 cancel:async(id:string,reason:string,notes?:string)=>(await axiosInstance.post<SellerOrder>(`${ROOT}/${id}/request-cancellation`,{reason,notes:notes||null})).data,
 messages:async(id:string)=>(await axiosInstance.get<SellerOrderMessage[]>(`/seller/orders/${id}/messages`)).data,
 sendMessage:async(id:string,payload:SellerOrderMessageCreate)=>(await axiosInstance.post<SellerOrderMessage>(`/seller/orders/${id}/messages`,payload)).data,
 package:async(id:string)=>(await axiosInstance.get<SellerOrderPackage>(`/seller/orders/${id}/package`)).data,
 savePackage:async(id:string,payload:SellerOrderPackageUpsert)=>(await axiosInstance.put<SellerOrderPackage>(`/seller/orders/${id}/package`,payload)).data,
};
