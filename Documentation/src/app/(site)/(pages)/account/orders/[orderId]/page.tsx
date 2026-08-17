import BuyerOrderDetails from "@/components/BuyerAccount/BuyerOrderDetails";
export default async function Page({params}:{params:Promise<{orderId:string}>}){const{orderId}=await params;return <BuyerOrderDetails orderId={orderId}/>}
