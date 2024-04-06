use serde_json::Value;
use syn::{Item, ReturnType, Type};

/// Input Content Example:
///     {"api":"fn try_unwrap(this: Self) -> Result<T, Self>","duration":0,"head":"Methods","impl":"impl<T> Arc<T>","next_api_index":-1,"stability":[],"submodule":"alloc::arc::Arc"}
pub fn is_api_same(api1: &Value, api2: &Value) -> bool {
    api1["impl"] == api2["impl"] && api1["api"] == api2["api"]
}

pub fn is_api_similar(api1: &Value, api2: &Value) -> bool {
    let impl1 = api1["impl"].as_str().unwrap();
    let impl2 = api2["impl"].as_str().unwrap();
    // TODO: Add impl parsing and comparison. Impls should be the same (not completely) rather than similar.
    let api1_sig = api1["api"].as_str().unwrap();
    let api2_sig = api2["api"].as_str().unwrap();
    // TODO: Add API signature parsing and comparison. APIs can be different but similar.
    true
}

/// If the impls are different but just an alias, we can consider them as the same.
pub fn is_impl_same(api1: &Value, api2: &Value) -> bool {
    if(api1["impl"] == api2["impl"]){
        return true;
    }
    let impl1 = api1["impl"].as_str().unwrap();
    let impl2 = api2["impl"].as_str().unwrap();
    true
}



#[derive(Debug, PartialEq, Eq)]
pub struct ApiSignature {
    pub ty: String,
    pub name: String,
    pub impls: Option<syn::Path>,
    pub generics: Vec<Type>,
    pub inputs: Vec<String>,
    pub output: String,
}

impl ApiSignature {
    pub fn new() -> Self {
        ApiSignature {
            ty: String::new(),
            name: String::new(),
            impls: None,
            generics: Vec::new(),
            inputs: Vec::new(),
            output: String::new(),
        }
    }

    pub fn get_impl_name(&self) -> Option<String> {
        Some(self.impls.clone()?.segments[0].ident.to_string())
    }
}



/// Given an API signature, parse it into a struct for comparison.
fn parse_api(api_sig: &str) -> Option<ApiSignature>{
    println!("Parsing API: {:#?}", api_sig);
    let item1:syn::Item = syn::parse_str(api_sig).expect("Failed to parse API signature");
    let mut api_signature = ApiSignature::new();
    println!("{:#?}", item1);
    match item1 {
        Item::Fn(item_fn) => {
            println!("Name: {:#?}", item_fn.sig.ident);
            println!("Generics: {:#?}", item_fn.sig.generics);
            println!("Inputs: {:#?}", item_fn.sig.inputs);
            println!("Output: {:#?}", item_fn.sig.output);
            // println!("Function inputs: {:?}", item_fn.sig.inputs);
            // println!("Function output: {:?}", item_fn.sig.output);
        }
        Item::Impl(item_impl) => {
            api_signature.impls = Some(item_impl.trait_?.1);
            println!("Generics: {:#?}", item_impl.generics.params);
            let target = item_impl.self_ty;
            {
                if let Type::Path(type_path) = *target {
                    api_signature.name = type_path.path.segments[0].ident.to_string();
                }
            }
            // println!("Target: {:#?}", target);
        }
        _ => return None,
    }
    return Some(api_signature);
}





#[allow(unused)]
fn parse_api_signature(signature: &str) -> Result<Item, syn::Error> {
    syn::parse_str(signature)
}

#[allow(unused)]
fn compare_api_signatures(sig1: &str, sig2: &str) -> bool {
    let item1 = match parse_api_signature(sig1) {
        Ok(item) => item,
        Err(_) => return false, // Return false if parsing fails
    };
    let item2 = match parse_api_signature(sig2) {
        Ok(item) => item,
        Err(_) => return false, // Return false if parsing fails
    };

    // Compare relevant parts of the API signatures
    match (&item1, &item2) {
        (Item::Fn(item_fn1), Item::Fn(item_fn2)) => {
            // Compare function names
            if item_fn1.sig.ident != item_fn2.sig.ident {
                return false;
            }

            // Compare parameter types
            if item_fn1.sig.inputs.len() != item_fn2.sig.inputs.len() {
                return false;
            }
            for (param1, param2) in item_fn1.sig.inputs.iter().zip(item_fn2.sig.inputs.iter()) {
                if !compare_types(&param1, &param2) {
                    return false;
                }
            }

            // Compare return types
            if !compare_return_types(&item_fn1.sig.output, &item_fn2.sig.output) {
                return false;
            }

            // Compare generics if needed

            // If all comparisons passed, return true
            true
        }
        _ => false, // Return false if items are not functions
    }
}

#[allow(unused)]
fn compare_types(type1: &syn::FnArg, type2: &syn::FnArg) -> bool {
    // Compare types of function arguments
    // Implement as needed
    true
}

#[allow(unused)]
fn compare_return_types(type1: &ReturnType, type2: &ReturnType) -> bool {
    // Compare return types of functions
    // Implement as needed
    true
}